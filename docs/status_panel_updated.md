# Hardware layout

Il pannello di stato e controllo principale è una piccola unità hardware, direttamente connessa al raspberri pi, che funge da strumento di interfaccia rudimentale e segnalazione sonoro e visivo per eventi interni all'animacharacter. Può loggare warning, info, crash totali. 

E' composto da:
- un LCD display
- un LED
- un encoder rotativo (manopola)
- un buzzer

### LCD 

Tutti i log appaiono sul pannello in questo formato:
` timestamp [WRN/INF/ERR code]: message`   
esempi:   
`12:30.5 [ERR 01]: Hardware manager crashed at boot`    
`70:13.2 [WRN b50]: Could not connect to head controller`    
`00:05.1 [ERR 00]: Missed hearthbeat from supervisor`   

I messaggi sono scrollabili con manopola, se il messaggio non entra in schermo, viene fatto scorrere quando evidenziato.
    +: cliccare sul messaggio fa vedere info aggiuntive

Tenere premuto il pulsante per piu di 5 secondi apre il meno di amministratore. Da qui sono disponibili
poche azioni, principalmente riavviare il sistema in caso di crash >> REBOOT SYSTEM

L'LCD si spegne se la manopola non è toccata per piu di un tot tempo.

### LED

Il led è un segnalatore di stato molto rudimentale. Codifica per vari stati
- SPENTO: sistema offline o crashato
- LAMPEGGIO LENTO: sistema online in attesa di connessione
- LAMPEGGIO VELOCE: connettendo...
- FISSO: sistema connesso e operativo
- LAMPEGGIO MEDIO: sistema acceso con errori da visualizzare (su LCD)

### buzzer

Il buzzer notifica l'utente dell'avvenimento di warning o errori. In generale, per un errore,
basta un buzz di 1-2 secondi. In alternativa, un buz periodico ogni 10s di 1-2 secondi fino a quando
l'errore non viene visualizzato da LCD, per una durata massima di 1-2minuti.

In caso di crash, il buzzer dovrebbe suonare tipo 4s on 4s off, fino a quando l'utente non riavvia o spegne il sistema.


### Altre considerazioni

Il riavvio eseguito sul pannello è un riavvio SW, significa che viene rilanciata l'immagine docker ma il pi rimane acceso.   

Per un riavvio HW (hard-reset), si possono avere switch ausiliari, anche sullo stesso pannello fisico, ma concettualmente sono cose diverse (cosi come gli switch per l'alimentazione o il current meter e volt meter).