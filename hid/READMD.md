Dataset

This dataset is for testing the keystroke injection detection daemon.

It has different parts:

- **Normal text**: regular words and sentences.  
  Example: `please review the meeting notes`

- **Normal shortcuts**: common shortcuts like copy, paste, save, and window switching.  
  Example: `CTRL+C`, `CTRL+V`, `CTRL+S`, `ALT+TAB`

- **Suspicious command-like text**: words that may be used in suspicious input.  
  Example: `cmd`, `powershell`, `whoami`, `sudo`, `curl`, `wget`

- **Hotkey + string sequences**: a hotkey followed by typed text.  
  Example: `GUI+R -> cmd`, `GUI+R -> powershell`

- **False positive tests**: normal sentences that contain suspicious-looking words.  
  Example: `the admin reviewed the server report`

- **Borderline/evasive tests**: modified suspicious strings that may not exactly match the blacklist.  
  Example: `power shell`, `p0wershell`, `c m d`, `who am i`
