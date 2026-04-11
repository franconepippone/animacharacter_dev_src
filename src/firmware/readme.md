This subfolder contains code related to the mcus (arduino, esp32, esp8266) used in the robot. It mainly consists of platformio projects (possibly one giant platformio project). While the rest of the repo is being developed on Ubuntu WSL, the platformio projects are best edited on windows due to native platformio support (WSL can be tricky). To perform a partial clone only of this folder on the windows machine, follow these steps:

## Working with only part of a Git monorepo using sparse checkout

The repo is not huge, so we’ll use **plain sparse checkout** (no partial clone).  
This keeps the full Git history locally, but your working directory will only contain the folders you choose.

Below are step‑by‑step instructions you can use both on **Windows** and **WSL/Ubuntu**.

---

## 0. Prerequisites

- **Git version**: ideally `>= 2.25` (for modern sparse-checkout behavior).
- You know:
  - The **repository URL**, e.g.  
    `https://github.com/you/your-monorepo.git`
  - The **subfolder(s)** you want to work on, e.g.  
    - `firmware/` for PlatformIO (Windows)  
    - `ros_ws/` for Ubuntu/WSL

You can adapt the paths below to your actual layout.

---

## 1. Clone the repository without checking out files

This creates the repo locally but does **not** populate the working tree yet.

```bash
git clone --no-checkout https://github.com/you/your-monorepo.git
cd your-monorepo
```

What this does:
- Downloads the full Git history and metadata.
- Leaves the working directory empty (no files checked out yet).
- Prepares the repo so we can enable sparse checkout before any files are written.
You can run this on:
- Windows (PowerShell / cmd)
- WSL/Ubuntu (bash)
The commands are the same.
