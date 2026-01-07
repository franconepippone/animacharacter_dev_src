This directory contains all python local custom packages, that
are installed inside the docker image using:

`python3 -m pip install --break-system-packages -e libs/pkg_name`

> This is not officially recommended, but it seems like it's the only way to achieve this simple thing.

NOTE: those packages are only used on the animacharacter's server software host machine,
they don't need to be shared with the client software.