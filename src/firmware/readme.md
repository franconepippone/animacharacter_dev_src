This subfolder contains code related to the mcus (arduino, esp32, esp8266) used in the robot. It mainly consists of platformio projects (possibly one giant platformio project). While the rest of the repo is being developed on Ubuntu WSL, the platformio projects are best edited on windows due to native platformio support (WSL can be tricky). 

> TL;DR: DO NOT EDIT THIS IF YOU ARE ON UBUNTU WSL, EDIT THIS FOLDER **ONLY** ON WINDOWS.

To perform a partial clone only of this folder on the windows machine, follow these steps:

Clone the repo with no checkout
```bash
git clone --no-checkout https://github.com/franconepippone/animacharacter_dev_src.git
```
```bash
cd animacharacter_dev_src
```

```bash
git sparse-checkout init
```
Only add the src/firmware subfolder
```bash
git sparse-checkout set src/firmware
```

```bash
git checkout <BRANCH-NAME>
```
Now the correct files should be downloaded