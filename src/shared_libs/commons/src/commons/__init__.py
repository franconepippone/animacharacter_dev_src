"""
Module containing all shared definitions, configurations and utilties between client and server.  
Provides unique source of truth for shared data. 

Version mistmatch of this package in client and server can lead (does lead) to incompatibilities. The installed versions
must match to ensure compatibilty.
"""


from .utils import ActTableEntry