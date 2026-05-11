This package is installed both onto the server and on the client. It exposes commons 
utilities and classes definition (i.e. network packet types) that needs to be shared
between both parts. It also contains configuration data (actuator -> id map for teodore), 
so that the source of truth is centralized and there are no duplicates of the same data. 