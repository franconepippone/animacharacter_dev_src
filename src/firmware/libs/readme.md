In here we have all libraries for the mcu code. They are imported in platformio projects.


DEPRECATED! the libs folder is no longer needed, we are storing all libraries inside platformio_project/lib because of intellisense not working properly outside of a project. This is ok as long as we have only 1 platformio project. If for some reason we will ever need more, we can just add the library as a github dependency (should be fine) like this:
lib_deps =
    https://github.com/user/repo.git#subfolder=src/firmware/platformio_project/lib/LibraryToUse 