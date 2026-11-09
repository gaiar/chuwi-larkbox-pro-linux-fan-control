// SPDX-License-Identifier: GPL-2.0-only OR MIT
/* CHUWI LarkBox Pro GB01_ZW_1_07: bounded fan-off leases via native ACPI. */
#include <linux/acpi.h>
#include <linux/crc32.h>
#include <linux/dmi.h>
#include <linux/init.h>
#include <linux/jiffies.h>
#include <linux/kobject.h>
#include <linux/module.h>
#include <linux/slab.h>
#include <linux/mutex.h>
#include <linux/suspend.h>
#include <linux/sysfs.h>
#include <linux/workqueue.h>
#include "larkbox_control.hex"

#define LEASE_MS 3000
#define TICK_MS 250
/* Off stays below the firmware's own STMP=65 C on point and the 65 C guard. */
#define OFF_ADMISSION_MC 64000
#define EMERGENCY_MC 65000
#define PAD_OFF 0x44000200ULL
#define PAD_ON  0x44000201ULL

static bool allow_control;
module_param(allow_control, bool, 0400);
MODULE_PARM_DESC(allow_control, "Allow bounded fan-off leases; default read-only");
static DEFINE_MUTEX(fan_lock);
static struct kobject *fan_kobj;
static struct delayed_work guard_work;
static u32 helper_index;
static bool helper_loaded, off_requested, suspended, faulted;
static unsigned long deadline;
static const char *last_fault = "none";

static int read_acpi(char *path, u64 *value)
{
	unsigned long long result;
	acpi_status status = acpi_evaluate_integer(NULL, path, NULL, &result);

	if (ACPI_FAILURE(status))
		return -EIO;
	*value = result;
	return 0;
}

static int read_cpu(int *temp)
{
	u64 value;
	int ret = read_acpi("\\_SB.PCI0.TCPU.TMP1", &value);

	if (ret)
		return ret;
	/* Firmware CTOK uses 2732, as verified in the live DptfTab. */
	if (value < 2732 || value > 3832)
		return -ERANGE;
	*temp = (value - 2732) * 100;
	return 0;
}

static int set_output(bool on)
{
	union acpi_object argument = { .type = ACPI_TYPE_INTEGER };
	struct acpi_object_list args = { .count = 1, .pointer = &argument };
	unsigned long long result;
	acpi_status status;

	argument.integer.value = on;
	status = acpi_evaluate_integer(NULL, "\\LBCF", &args, &result);
	if (ACPI_FAILURE(status))
		return -EIO;
	return result == (on ? PAD_ON : PAD_OFF) ? 0 : -EIO;
}

/* Call with fan_lock held. Leaving SFAN=0 makes every native poll force ON. */
static int full_on(const char *reason)
{
	int ret;

	off_requested = false;
	deadline = 0;
	ret = set_output(true);
	if (reason || ret) {
		faulted = true;
		last_fault = ret ? "full_on_failed" : reason;
		pr_warn_ratelimited("larkbox_fan: %s (full-on result %d)\n",
				    last_fault, ret);
	}
	return ret;
}

static void guard_tick(struct work_struct *work)
{
	int temp, ret;

	mutex_lock(&fan_lock);
	if (off_requested) {
		ret = read_cpu(&temp);
		if (ret)
			full_on("temperature_read_failed");
		else if (temp >= EMERGENCY_MC)
			full_on("emergency_temperature");
		else if (time_after_eq(jiffies, deadline))
			full_on("lease_expired");
	}
	mutex_unlock(&fan_lock);
	schedule_delayed_work(&guard_work, msecs_to_jiffies(TICK_MS));
}

static ssize_t status_show(struct kobject *kobj, struct kobj_attribute *attr,
			   char *buf)
{
	u64 smart, threshold, pad;
	unsigned long remaining = 0;
	int temp, ret;

	mutex_lock(&fan_lock);
	ret = read_cpu(&temp);
	ret = ret ?: read_acpi("\\SFAN", &smart);
	ret = ret ?: read_acpi("\\STMP", &threshold);
	ret = ret ?: read_acpi("\\_SB.GPO0.TMPE", &pad);
	if (!ret) {
		if (off_requested && time_before(jiffies, deadline))
			remaining = jiffies_to_msecs(deadline - jiffies);
		ret = sysfs_emit(buf,
			"{\"cpu_millic\":%d,\"smart_fan\":%llu,\"threshold_c\":%llu,"
			"\"gpio_raw\":%llu,\"fan_on\":%u,\"off_requested\":%u,"
			"\"lease_remaining_ms\":%lu,\"control_enabled\":%u,"
			"\"fault\":\"%s\"}\n",
			temp, smart, threshold, pad, (unsigned int)(pad & 1),
			off_requested, remaining, allow_control, last_fault);
	}
	mutex_unlock(&fan_lock);
	return ret;
}

static ssize_t command_store(struct kobject *kobj, struct kobj_attribute *attr,
			     const char *buf, size_t count)
{
	bool on;
	int ret, temp;

	if (!allow_control)
		return -EPERM;
	if (sysfs_streq(buf, "on"))
		on = true;
	else if (sysfs_streq(buf, "off"))
		on = false;
	else
		return -EINVAL;
	mutex_lock(&fan_lock);
	if (on) {
		ret = full_on(NULL);
		if (!ret) {
			faulted = false;
			last_fault = "none";
		}
	} else if (suspended || faulted) {
		ret = -EBUSY;
	} else {
		ret = read_cpu(&temp);
		if (ret || temp >= OFF_ADMISSION_MC) {
			full_on(ret ? "temperature_read_failed" : "off_above_limit");
			ret = ret ?: -ERANGE;
		} else {
			ret = set_output(false);
			if (ret) {
				full_on("off_command_failed");
			} else {
				off_requested = true;
				deadline = jiffies + msecs_to_jiffies(LEASE_MS);
			}
		}
	}
	mutex_unlock(&fan_lock);
	return ret ?: count;
}

static struct kobj_attribute status_attr = __ATTR_RO(status);
static struct kobj_attribute command_attr = __ATTR(command, 0200, NULL, command_store);
static struct attribute *fan_attrs[] = {
	&status_attr.attr, &command_attr.attr, NULL
};
static const struct attribute_group fan_group = { .attrs = fan_attrs };

static int pm_event(struct notifier_block *nb, unsigned long event, void *unused)
{
	mutex_lock(&fan_lock);
	switch (event) {
	case PM_SUSPEND_PREPARE:
	case PM_HIBERNATION_PREPARE:
	case PM_RESTORE_PREPARE:
		suspended = true;
		full_on("suspend");
		break;
	case PM_POST_SUSPEND:
	case PM_POST_HIBERNATION:
	case PM_POST_RESTORE:
		suspended = false;
		full_on("resume_requires_restart");
		break;
	}
	mutex_unlock(&fan_lock);
	return NOTIFY_OK;
}
static struct notifier_block pm_notifier = { .notifier_call = pm_event };

static bool contains_once(const u8 *data, size_t length,
			  const u8 *pattern, size_t size)
{
	size_t i;
	unsigned int hits = 0;

	for (i = 0; i + size <= length; i++)
		if (!memcmp(data + i, pattern, size))
			hits++;
	return hits == 1;
}

static int verify_firmware(void)
{
	/* AML OpRegion TMPN at D0C509E0, followed by 32-bit field TMPE. */
	static const u8 region[] = {
		0x5b, 0x80, 'T', 'M', 'P', 'N', 0x00, 0x0c,
		0xe0, 0x09, 0xc5, 0xd0, 0x0a, 0x08,
		0x5b, 0x81, 0x0b, 'T', 'M', 'P', 'N', 0x03,
		'T', 'M', 'P', 'E', 0x20
	};
	struct acpi_table_header *table;
	acpi_status status;
	u64 smart, threshold, pad;
	bool found = false;
	int i, temp;

	if (!dmi_match(DMI_SYS_VENDOR, "CHUWI Innovation And Technology(ShenZhen)co.,Ltd") ||
	    !dmi_match(DMI_PRODUCT_NAME, "LarkBox Pro") ||
	    !dmi_match(DMI_BIOS_VERSION, "GB01_ZW_1_07"))
		return -ENODEV;
	status = acpi_get_table(ACPI_SIG_DSDT, 1, &table);
	if (ACPI_FAILURE(status))
		return -ENODEV;
	found = contains_once((u8 *)table, table->length, region, sizeof(region));
	acpi_put_table(table);
	if (!found)
		return -ENODEV;
	found = false;
	for (i = 1; i <= 64; i++) {
		status = acpi_get_table(ACPI_SIG_SSDT, i, &table);
		if (ACPI_FAILURE(status))
			break;
		/* Compatibility fingerprint, not a security/authentication checksum. */
		if (table->length == 17231 &&
		    (crc32_le(~0U, (u8 *)table, table->length) ^ ~0U) == 0x434cda59)
			found = true;
		acpi_put_table(table);
	}
	if (!found || read_acpi("\\SFAN", &smart) || smart > 1 ||
	    read_acpi("\\STMP", &threshold) || threshold > 110 ||
	    read_acpi("\\_SB.GPO0.TMPE", &pad) ||
	    (pad != PAD_OFF && pad != PAD_ON) || read_cpu(&temp))
		return -ENODEV;
	return 0;
}

/* ACPICA retains table descriptors after unload. Keep a heap-backed table
 * resident and reuse it on reload, never a pointer into unloadable module data.
 */
static int load_helper(void)
{
	struct acpi_table_header *table;
	acpi_status status;
	int i;

	for (i = 1; i <= 128; i++) {
		status = acpi_get_table(ACPI_SIG_SSDT, i, &table);
		if (ACPI_FAILURE(status))
			break;
		if (table->length == sizeof(larkbox_control_aml_code) &&
		    !memcmp(table, larkbox_control_aml_code, sizeof(larkbox_control_aml_code))) {
			status = acpi_load_table(table, &helper_index);
			acpi_put_table(table);
			return ACPI_FAILURE(status) ? -EIO : 0;
		}
		acpi_put_table(table);
	}
	table = kmemdup(larkbox_control_aml_code, sizeof(larkbox_control_aml_code), GFP_KERNEL);
	if (!table)
		return -ENOMEM;
	/* Also retain on a load error: ACPICA may have installed the descriptor. */
	status = acpi_load_table(table, &helper_index);
	return ACPI_FAILURE(status) ? -EIO : 0;
}

static int __init larkbox_init(void)
{
	acpi_handle existing;
	int ret = verify_firmware();

	if (ret) {
		pr_err("larkbox_fan: unsupported hardware or ACPI fingerprint\n");
		return ret;
	}
	if (allow_control) {
		if (ACPI_SUCCESS(acpi_get_handle(NULL, "\\LBCF", &existing)))
			return -EEXIST;
		ret = load_helper();
		if (ret)
			return ret;
		helper_loaded = true;
		ret = full_on(NULL);
		if (ret)
			goto unload;
		ret = register_pm_notifier(&pm_notifier);
		if (ret)
			goto unload;
	}
	fan_kobj = kobject_create_and_add("larkbox_fan", kernel_kobj);
	if (!fan_kobj) {
		ret = -ENOMEM;
		goto unregister;
	}
	ret = sysfs_create_group(fan_kobj, &fan_group);
	if (ret) {
		kobject_put(fan_kobj);
		goto unregister;
	}
	if (allow_control) {
		INIT_DELAYED_WORK(&guard_work, guard_tick);
		schedule_delayed_work(&guard_work, msecs_to_jiffies(TICK_MS));
	}
	pr_info("larkbox_fan: %s; verified GB01_ZW_1_07 ACPI\n",
		allow_control ? "control enabled; full on" : "read-only");
	return 0;
unregister:
	if (allow_control)
		unregister_pm_notifier(&pm_notifier);
unload:
	if (helper_loaded) {
		full_on("initialization_failed");
		acpi_unload_table(helper_index);
	}
	return ret;
}

static void __exit larkbox_exit(void)
{
	sysfs_remove_group(fan_kobj, &fan_group);
	if (allow_control) {
		unregister_pm_notifier(&pm_notifier);
		cancel_delayed_work_sync(&guard_work);
		mutex_lock(&fan_lock);
		full_on(NULL);
		mutex_unlock(&fan_lock);
		if (ACPI_FAILURE(acpi_unload_table(helper_index)))
			pr_err("larkbox_fan: failed to unload helper table\n");
	}
	kobject_put(fan_kobj);
}
module_init(larkbox_init);
module_exit(larkbox_exit);
MODULE_LICENSE("Dual MIT/GPL");
MODULE_AUTHOR("gaiar and contributors");
MODULE_DESCRIPTION("LarkBox Pro GPIO fan control with bounded off leases and ACPI fallback");
MODULE_VERSION("0.2.0");
