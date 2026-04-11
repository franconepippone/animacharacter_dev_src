#pragma once
#include <Arduino.h>
#include "utility/vectors.h"
#include "utility/controllers/quad_2d_lerper.h"

/* Permette il controllo differenziale di 2 attuatori con l'ottenimento di 2 gradi di libertà; 
Utile in giunti a 2dof controllati da 2 motori (ES.: collo animatronico).

L'argomento del template specifica il tipo di dato con cui è specificata la posizione degli attuatori (int, uint, float..)

Utilizza Quad2DLerper per l'interpolazione lineare dei comandi, quindi il dominio dell'input è: |y| < 1-|x|
*/
template <typename T = float>
class ActuatorDiffPair {
private:

    vec2<T> current_action;
    Quad2DLerper<2> lerper;

public:
    ActuatorDiffPair(vec2<T> REST, vec2<T> UP, vec2<T> DOWN, vec2<T> LEFT, vec2<T> RIGHT) : current_action(REST) {
        // converte i vec2<T> in float2 e li passa nei buffer dei vertici del lerper
        float2 rest(REST);
        float2 up(UP);
        float2 down(DOWN);
        float2 left(LEFT);
        float2 right(RIGHT);
        lerper = Quad2DLerper<2>(rest.get_array(), up.get_array(), right.get_array(), down.get_array(), left.get_array());
    };

    vec2<T> control(float2 input) {
        float2 output;
        lerper.interpolate(input, output.get_array());
        current_action.x = output.x; // effettua i casting in automatico se necessario;
        current_action.y = output.y;
        return current_action;
    }

    // Returns the position of the actuators calculated on the last call of "control"
    vec2<T> get_last_action() {return current_action;}
};