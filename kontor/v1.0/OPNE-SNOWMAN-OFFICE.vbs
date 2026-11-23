' SNOWMAN by Alpindata - SNOWMAN Office: opnar kart og anlegg (snarvegen paa skrivebordet).
' Svarar ikkje SNOWMAN Office, blir tenesta starta (eller START-SNOWMAN-OFFICE.bat), og vindauget opnar naar ho svarar.
' Opnar i eige vindauge (Microsoft Edge eller Google Chrome i app-modus), elles i standard nettlesar.
Option Explicit
Dim sh, fso, here, url, i, ok
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
url = "http://localhost:8765/"

Function Svarar()
  Dim x
  Svarar = False
  On Error Resume Next
  Set x = CreateObject("MSXML2.ServerXMLHTTP.6.0")
  x.setTimeouts 1500, 1500, 2000, 2000
  x.open "GET", url & "api/status", False
  x.send
  If Err.Number = 0 Then
    If x.status = 200 Then Svarar = True
  End If
  Err.Clear
  On Error GoTo 0
End Function

If Not Svarar() Then
  ' tenesta (installert med INSTALLER-WINDOWS.bat) - nytt namn, og det gamle fraa foer 1.2.0
  sh.Run "schtasks /run /tn ""SNOWMAN Office""", 0, True
  sh.Run "schtasks /run /tn ""SNOWMAN Kontor""", 0, True
  For i = 1 To 15
    WScript.Sleep 2000
    If Svarar() Then Exit For
  Next
  If Not Svarar() Then
    ' inga teneste: start Office i eit eige (minimert) vindauge
    sh.Run """" & here & "\START-SNOWMAN-OFFICE.bat""", 7, False
    For i = 1 To 45
      WScript.Sleep 2000
      If Svarar() Then Exit For
    Next
  End If
End If

If Not Svarar() Then
  MsgBox "SNOWMAN Office svarar ikkje enno." & vbCrLf & vbCrLf & _
         "Foerste gong kan det ta eit par minutt (pakkane til kartet blir installerte). Proev snarvegen igjen om litt." & vbCrLf & _
         "Hjelper ikkje det: koeyr START-SNOWMAN-OFFICE.bat i mappa " & here & " og sjaa kva som staar der.", _
         vbExclamation, "SNOWMAN Office"
  WScript.Quit 1
End If

Dim pf, pf86, la, kand, k
pf = sh.ExpandEnvironmentStrings("%ProgramFiles%")
pf86 = sh.ExpandEnvironmentStrings("%ProgramFiles(x86)%")
la = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%")
kand = Array(pf86 & "\Microsoft\Edge\Application\msedge.exe", pf & "\Microsoft\Edge\Application\msedge.exe", _
             pf & "\Google\Chrome\Application\chrome.exe", pf86 & "\Google\Chrome\Application\chrome.exe", _
             la & "\Google\Chrome\Application\chrome.exe")
For Each k In kand
  If fso.FileExists(k) Then
    sh.Run """" & k & """ --app=" & url & " --start-maximized", 1, False
    WScript.Quit 0
  End If
Next
sh.Run url, 1, False
