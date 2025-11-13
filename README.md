## Rag Prototype for First Year Scholar 2025
### Building and Running
#### WSL
In order to get running on Windows, you first need to setup WSL
because the vector database used (pymilvus-lite) isn't supported on Windows

You can view the installation instructions on the [windows website](https://learn.microsoft.com/en-us/windows/wsl/install),
or you can run the commands listed below in the windows terminal/ powershell
```ps
wsl --install
```

After this run
```ps
wsl.exe --list --online
```

to install the latest version of Ubuntu using
```ps
wsl.exe --install [name of latest Ubuntu version]
```

From here, it should walk you through the steps for setting up this linux distribution.
Absolutely make sure that you set a superuser password though.

#### Setting up UV
UV is a pip alternative that supports, and automatically updates, pyproject.toml files.
It's also much faster, so it's primarily used to keep build times low. I'm tailoring this guide
towards pycharm because it's the IDE that I use, but it shouldn't be difficult to adapt it
to other IDEs.

Open up the terminal in pycharm, click the `v` (down arrow) button at the top of the pane,
and select ubuntu. Once the terminal opens, run
```bash
sudo apt update
sudo apt-get upgrade
sudo apt install pipx
```

Once pipx is installed, use it to install UV. Why do you need to install pipx? Idk,
they recommended it on their website, so I'd recommend it as well I guess. Anyways, run
the following command to install UV.
```bash
pipx install uv
```

#### Post-uv installation
Once uv is installed run `uv sync` to make sure that you have the correct packages installed.
Then, you're done! You can run `main.py` using `uv run main.py`.

## Note:
The installation steps may change drastically once I fully get fastapi going. Be
sure to run uv sync every once in a while to make sure your packages are up-to-date
as well.
