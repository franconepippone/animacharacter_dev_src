Ecco un resoconto tecnico dell'architettura di codifica per il pannello di diagnostica locale, progettata per massimizzare la leggibilità su un display a 3 cifre e garantire la robustezza del sistema.

### 1. Filosofia di Codifica (Display a 7 segmenti, 3 cifre)
La codifica segue lo schema **Soggetto-Predicato** per permettere un'identificazione istantanea della sorgente e della gravità dell'errore. Per evitare ambiguità dovute alla natura dei display a 7 segmenti, i prefissi alfabetici sono stati limitati e riservati.

*   **Fxx (Fatal Errors):** Errori critici che causano lo shutdown del sistema. Il display rimane fisso sul codice.
    *   *Esempi:* `F00` (Crash del Supervisor), `F01` (Crash del CORE/Hardware Manager).
*   **Exx (System Warnings):** Errori di sistema non fatali o processi in fase di respawn.
    *   *Esempi:* `E03` (WebUI offline), `E30` (Servizio unresponsive).
*   **y.xx (Driver/Controller Errors):** Errori specifici provenienti dai plugin hardware.
    *   **y**: ID del Driver (0-9, A-D esadecimale, per un massimo di 14 driver).
    *   **xx**: Codice errore specifico del driver (00-99).
    *   **Punto Decimale**: Il punto dopo la prima cifra funge da separatore semantico per distinguere immediatamente un errore driver da uno di sistema, anche in caso di segmenti danneggiati.

### 2. Gestione degli Stati e Feedback Visivo/Sonoro
Il sistema utilizza una combinazione di LED RGB e Buzzer per fornire una gerarchia di allerta:

| Stato | LED RGB | Buzzer | Comportamento Display |
| :--- | :--- | :--- | :--- |
| **Nominale** | Verde Fisso | Silenzio | `---` o Heartbeat |
| **Warning** | Giallo Pulsante | 1 Beep breve (al nuovo evento) | Carousel degli errori attivi |
| **Fatale** | Rosso Lampeggiante | 3 Beep lunghi all'attivazione | Codice `Fxx` fisso |

### 3. Logica di Instradamento e "Warning Carousel"
Dato che il display è limitato, il **Supervisor** funge da aggregatore e mappatore dinamico:
*   **Mappatura Driver:** Il Supervisor riceve messaggi da `/diagnostics`, identifica il nodo mittente e lo associa a un `DriverID` (es. "Braccio" -> ID 2). Traduce il codice locale del driver in formato `2.xx`.
*   **Carousel:** Se sono presenti più warning contemporaneamente, il Supervisor pubblica una lista su `/system_status`. Il nodo driver dello Status Panel cicla la visualizzazione (es. 2 secondi per codice).
*   **Priorità:** Gli errori fatali (`Fxx`) hanno la precedenza assoluta e interrompono qualsiasi ciclo di warning.

### 4. Meccanismi di Fail-Safe (Watchdog)
L'architettura garantisce la segnalazione anche in caso di fallimento dei componenti principali:
*   **Crash del Supervisor:** Gestito direttamente dal **Launch System** tramite `OnProcessExit`. All'uscita del processo, il launch esegue un comando CLI one-shot che pubblica forzatamente `F00` su `/system_status`.
*   **Segnale "I'M ALIVE":** Il Supervisor invia un battito cardiaco costante. Se il pannello non riceve aggiornamenti per un tempo X, mostra autonomamente un errore di timeout (`F00` o codice di link perso), notificando che il "cervello" non sta più comunicando.

### 5. Standardizzazione per lo Sviluppatore
Per mantenere il sistema estensibile tramite plugin:
1.  I driver pubblicano errori su `/diagnostics` con un codice locale (0-99).
2.  Il Supervisor è l'unico componente a conoscere la topologia totale e ad assegnare gli ID driver per il pannello.
3.  Non è richiesto alcun coordinamento tra sviluppatori di driver diversi per evitare sovrapposizioni di codici, poiché il "dominio" è garantito dal prefisso `y.` assegnato dal Supervisor.