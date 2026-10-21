/* SPDX-License-Identifier: GPL-2.0-only OR MIT */
DefinitionBlock ("", "SSDT", 2, "LBXFAN", "CONTROL", 1)
{
    External (\SFAN, FieldUnitObj)
    External (\STMP, FieldUnitObj)
    External (\_SB.GPO0.TMPE, FieldUnitObj)
    External (\_SB.SEN4._TMP, MethodObj)

    // Called only after the kernel's board, firmware and temperature checks.
    // The native firmware remains able to turn cooling on above 65 C.
    Method (LBCF, 1, Serialized)
    {
        If (Arg0 == One)
        {
            \SFAN = Zero
        }
        Else
        {
            \STMP = 65
            \SFAN = One
        }
        \_SB.SEN4._TMP ()
        Return (\_SB.GPO0.TMPE)
    }
}
