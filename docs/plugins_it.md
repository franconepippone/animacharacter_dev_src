# Architettura Plug-in

*Animacharacter Engine* è un sistema altamente basato su plugin. L'adattamento del motore a uno specifico
caso d'uso (es. una piattaforma robotica / hardware personalizzata) e l'estenzione con funzionalità aggiuntive 
viene fatto interamente tramite plugin.

Di fatto, senza plugin, il motore è un cervello "senza mani". L'abilità del motore di interfacciarsi
con l'hardware è fornita proprio da plugin, ed è a carico dell'utente scrivere plugin che gli permettano di farlo. 

Questo è il motivo per cui *Animacharacter Engine* può essere utilizzato per qualsiasi piattaforma robotica.

## Cos'è un plugin?

Un plugin in questo caso non è altro che un modulo python scritto dall'utente, che viene dinamicamente caricato ed eseguito dal sistema.

All'utente è chiesto in genere di definire classi o funzioni, che seguano determinate interfacce e standard, che poi vengono
importante dinamicamente e utilizzate all'interno del software. 