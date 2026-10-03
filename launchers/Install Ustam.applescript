-- Open this UTF-8 source in Script Editor and click Run yourself.
-- This builds locally; it never removes quarantine or changes Gatekeeper.
set jobFolder to ""
set helperPath to ""
set pythonPath to ""
try
    display dialog "Ustam yerel kaynak kurulumu / Local source installation\n\nKaynak klasörünü seçin. Python 3.11+ ve internet gerekir. Proje ve kayıtlı Ustam verileri değiştirilmez. / Select the extracted source folder. Python 3.11+ and internet are required. Project and saved Ustam data are preserved." buttons {"İptal / Cancel", "Devam / Continue"} default button 2 cancel button 1
    set sourceFolder to POSIX path of (choose folder with prompt "Ustam kaynak klasörü / Ustam source folder (scripts, launchers, ustam)")
    set helperPath to sourceFolder & "scripts/install_ustam_macos.py"
    set candidates to {"/Library/Frameworks/Python.framework/Versions/Current/bin/python3", "/opt/homebrew/bin/python3", "/usr/local/bin/python3"}
    repeat with candidate in candidates
        try
            set answer to do shell script quoted form of candidate & " -I -c " & quoted form of "import sys; print(int(sys.version_info >= (3, 11)))"
            if answer is "1" then
                set pythonPath to candidate as text
                exit repeat
            end if
        end try
    end repeat
    if pythonPath is "" then
        display dialog "Python 3.11+ bulunamadı / Python 3.11+ was not found.\nResmi Python macOS kurucusunu kurun, sonra bu kaynağı tekrar çalıştırın. / Install official Python for macOS, then run this source again." buttons {"İptal / Cancel", "Python indirme / Download Python"} default button 2 cancel button 1
        open location "https://www.python.org/downloads/macos/"
        return
    end if
    set jobFolder to do shell script quoted form of pythonPath & " -I " & quoted form of helperPath & " --start " & quoted form of sourceFolder
    set progress total steps to -1
    set progress description to "Ustam yerel kurulum / Local installation"
    repeat
        set statusText to do shell script quoted form of pythonPath & " -I " & quoted form of helperPath & " --status " & quoted form of jobFolder
        set statusLines to paragraphs of statusText
        set phase to item 1 of statusLines
        set detail to ""
        if (count statusLines) > 1 then set detail to item 2 of statusLines
        set progress additional description to detail
        if phase is "done" then
            set progress total steps to 0
            display dialog "Ustam yerel olarak kuruldu / Installed locally.\n" & detail & "\n\nAçmak, mevcut kullanıcı Ustam kayıtlarını kullanır. / Opening uses your existing Ustam state." buttons {"Kapat / Close", "Ustam aç / Open Ustam"} default button 2
            if button returned of result is "Ustam aç / Open Ustam" then do shell script "/usr/bin/open -n " & quoted form of detail
            exit repeat
        end if
        if phase is "error" then error detail
        delay 1
    end repeat
on error errorText number errorNumber
    set progress total steps to 0
    if jobFolder is not "" then
        try
            do shell script quoted form of pythonPath & " -I " & quoted form of helperPath & " --cancel " & quoted form of jobFolder
        end try
    end if
    if errorNumber is not -128 then display dialog "Kurulum tamamlanmadı / Installation did not complete.\n" & errorText buttons {"Tamam / OK"} default button 1
end try
