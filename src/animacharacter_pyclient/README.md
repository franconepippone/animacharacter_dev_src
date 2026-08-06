if you are developing this and you need the local dependencies to be editable, please run 
uv add -r ./dev-requirements.txt 
This will install all packages listed in the dev-requirements.txt file as editable, overriding the default github source on the pyproject.toml

If this is a deployed library, then the pyproject.toml should ideally already point to the github sources, but in case that does not work, run
uv add -r ./deploy-requirements.txt
this will override the dependecies source on the pyproject.toml with github sources. Ideally, this should be run prior to any major release commit, so that the pyproject is in good shape on github.