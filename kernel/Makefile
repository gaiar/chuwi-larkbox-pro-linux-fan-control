obj-m += larkbox_fan.o
KDIR ?= /lib/modules/$(shell uname -r)/build
.PHONY: all clean
all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) W=1 KCFLAGS=-Werror modules
clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) clean
