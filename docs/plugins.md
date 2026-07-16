
# Plugin architecture

The *Animacharacter Engine* is entirely customizable by user-written plugins. As a matter of fact, without plugins,
the engine would be completely incapable of interacting with hardware; the interface between user-specific hardware
and the engine is intirely implement by user-written plugins.

What follows is the recommended workflow for running and deploying a system with plugins. For in depth documentation on
how to write good plugins for the desired plugin category, see ...

#### But what's a plugin?

A plugin in this context is just a python module that is written by an 
external user, loaded and runned dynamically by the system to implement a desired functionality.


## Standard setup

The Docker image exposes a `/plugins` directory (located in `/app/plugins`): this directory is what contains all user-written plugins. Plugins
placed in this directory will be automatically registered by the system, and can be referenced in the appropriate
`configuration` file.

The directory is divided into subdirectories, one for each plugin category:
```
/plugins
    /hardware_controllers/...
    /behaviors/...
```
> Note: plugins must be put inside the respective *subdirectory*, not directly under `/plugins`.

The `/plugins` directory can either be mounted on the container, or can be edited directly inside it, according
to developer preferences.

#### How to run plugins

Plugins put inside these folder is **not** automatically loaded and executed. Instead, to define what plugins
will actually be launched, the system relies on `configuration.yaml` files. 
Each subfolder inside the `/plugins` directory must contain such a file. The name and internal structure of this file may change between different plugin category.

For example, for *hardware_controllers*, you might have:
```
/plugins
    /hardware_controllers/
        my_controllers_1.py
        my_controllers_2.py
        hw_configurations.yaml  <--- CONFIGURATION FILE
```
In this file, multiple launch configurations can be defined by referencing plugins. At system launch, one of these configurations is 
selected and loaded, usually declared under `default_configuration`. For exact guide on writing *hardware_controllers* plugins, see ...


## Custom setup (advanced)

This section explains the deeper inner workings of the plugin searching and loading system. This knowldege can be used to
create customizable development setups, that do not follow the *Standard-Setup* guide. 

> NOTE: if you are not planning on deviating from the standard setup, this section can be ignored.

For each plugin category (i.e. hardware_controller), the system generally looks for two environment variables:   
`HW_CONTROLLER_PLUGIN_PATHS`  
`HW_CONTROLLER_CONFIGS`

These environment variables contain lists of double-dot (':') separated system paths. Very simply, on boot, all paths found on `HW_CONTROLLER_PLUGIN_PATHS` are
put on *sys.path*, allowing python to import them as modules. `HW_CONTROLLER_CONFIGS` is a list of paths pointing to possible `hw_configurations.yaml` files; the last one found is the one used.

By default, `HW_CONTROLLER_PLUGINS_PATH` contains `/plugins/hardware_controllers` and possibly a path to the builtin plugins (joined by ':' separator).
Similarily, `HW_CONTROLLER_CONFIGS` contains `/plugins/hardware_controllers/hw_configurations.yaml` (expected location of user-defined config file), and possibly a path to a builtin configuration file. This last file comes first, meaning that if the expected used-written config exists, it will be the one used, overriding the builtin config.

There is no limit to the amount of paths that can be stored and processed by this mechanism. This is also how the standard-setup works.

Jnowing this, These environment variables can be changed, making possible to create custom development setups for plugins.

## Writing Hardware Controllers

For driving specific hardware, custom hardware controllers plugins are required. Those are loaded at runtime
as defined by a *configuration* file. Controllers can subscribe ("listen") to client commands, and their job is to 
translate these commands into hardware action. 