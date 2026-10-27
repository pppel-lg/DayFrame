; Keep the default application installation separate from personal archives.
; Tauri's currentUser template otherwise uses $LOCALAPPDATA\DayFrame itself.
!macro NSIS_HOOK_PREINSTALL
  ${If} $INSTDIR == "$LOCALAPPDATA\DayFrame"
    StrCpy $INSTDIR "$LOCALAPPDATA\Programs\DayFrame"
    ; The template selected OUTDIR before this hook. Update both values.
    SetOutPath "$INSTDIR"
  ${EndIf}
!macroend
