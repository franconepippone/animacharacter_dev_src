# Architettura Plug-in

*Animacharacter Engine* è un sistema basato su plugin. L'adattamento del motore a uno specifico
caso d'uso (es. una piattaforma robotica / hardware personalizzata) e l'estenzione con funzionalità aggiuntive 
viene fatto interamente tramite plugin.

Di fatto, senza plugin, il motore è un cervello "senza mani". L'abilità del motore di interfacciarsi
con l'hardware è fornita proprio da plugin, ed è a carico dell'utente scrivere plugin che gli permettano di farlo. 

## Cos'è un plugin?

Un plugin è un file .py che viene caricato a runtime, e in cui sono presenti definizioni di funzioni o classi di cui il software potrà fare uso.

Esistono due tipi di plugin:

### 1. Controllers
I controller sono classi che implementano dei metodi chiamati periodicamente per effettuare il controllo dell'hardware. 


All'utente è chiesto in genere di definire classi o funzioni, che seguano determinate interfacce e standard, che poi vengono
importante dinamicamente e utilizzate all'interno del software. 