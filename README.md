## Rag Prototype for First Year Scholar 2025
### Building and Running
#### Supported Platforms
If running on MacOS, you can just skip to Setting up UV. Unfortunately, the project does not support
linux, so it cannot run on that platform. If on Linux, follow the instructions in the following section:

#### Environment file
Before running the backend, first create a .env file in the root of the project, and add the following
variables to it.

```dotenv
AI_MODEL=deepseek-r1:8b
POI_JSON_PATH=NavigationFireDynamicMesh_POIs.json
DB_URL=database.db
```

You may put whatever AI model you'd like for the `AI_MODEL` field, however please ensure you have this installed
within ollama

#### POI JSON Information
Before continuing, make sure you export the POIs as json. To do this, go to the NavigationFireDynamicMesh scene
using the instructions in the repository for the Unity project, then open the project, click on POITools and
click export. In the file picker, navigate to the root of the backend project, then click save.

#### Running on Docker:
In order to setup the docker, ensure you have downloaded and installed [Docker Desktop](https://www.docker.com/products/docker-desktop/)
and followed their setup directions. Once setup, go to the project in pycharm (you may need to clone
the repository if not already done), and open the terminal. In the terminal, run the following:
```bash
docker compose up
```
When you run this command, it will automatically run and setup the entire backend. There have been
issues with this so be warned.

Congrats, you are now able to run the project! If you wish to edit the project in Pycharm, please
follow the instructions below.

#### Setting up UV
There are two different methods for installing and running pip. If you are using pycharm, I reccomend
installing it through pycharm. Otherwise, follow the command line instructions.

##### Through Pycharm
Once you've loaded the project, go to the settings cog in the top right and press settings, or alternatively, press
`CTRL+ALT+S` to enter the settings menu. Once in the settings menu, double click on python, then click on
interpreter in the side bar. Click Add interpreter, then add local interpreter. Then click the dropdown next to type,
then press UV. If you get a prompt that UV is not installed, click install via pip. Once it is done installing click ok,
then you should be able to continue with the instructions below.

##### Through the Command Line
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
Then, you're done! You can then run the project by running the command `uv run fastapi run`.

## Note:
The installation steps may change drastically once I fully get fastapi going. Be
sure to run uv sync every once in a while to make sure your packages are up-to-date
as well.
