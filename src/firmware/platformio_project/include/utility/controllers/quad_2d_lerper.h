#pragma once
#include <Arduino.h>
#include "utility/vectors.h"

template <typename T> int sign(T val) {
    return (T(0) < val) - (val < T(0));
}

/* Effettua un interpolazione lineare su una mesh di quattro triangoli rettangoli isosceli:
T1(v1, v0, v2), T2(v2, v0, v3), T3(v3, v0, v4), T4(v4, v0, v1),
dove i vertici v0, v1, v2, v3, v4 sono collocati rispettivamente in (0,0) (0,1) (1,0) (0,-1) (-1,0).

A ogni vertice è associato un float buffer di dimensione BUFF_SIZE; alla chiamata di interpolate(...), i contenuti
dei buffer vengono interpolati linearmente sulla mesh in base alle coordinate di input.

Il dominio dell'input è |y| < 1 - |x| (Rombo di semidiagonale 1 centrato nell'origine).
Input esterni al dominio vengono automaticamente ristretti.
*/
template <size_t BUFF_SIZE>
class Quad2DLerper {
private:
    float _v0_data[BUFF_SIZE];
    float _v1_data[BUFF_SIZE];
    float _v2_data[BUFF_SIZE];
    float _v3_data[BUFF_SIZE];
    float _v4_data[BUFF_SIZE];

    inline bool is_in_domain(float2 a) const {
        return abs(a.y) <= 1.0 - abs(a.x);
    }

    inline float2 restrict_input(float2 in) const {
        in.x = constrain(in.x, -1.0f, 1.0f);
        in.y = constrain(in.y, -1.0f, 1.0f);

        return float2(sign(in.x) * 0.5 * (1.0 + abs(in.x) - abs(in.y)), sign(in.y) * 0.5 * (1.0 - abs(in.x) + abs(in.y)));
    }
    
public:
    Quad2DLerper() {
       for (size_t i = 0; i < BUFF_SIZE; i++) {
            _v0_data[i] = 0;
            _v1_data[i] = 0;
            _v2_data[i] = 0;
            _v3_data[i] = 0;
            _v4_data[i] = 0;
        }  
    }
    
    Quad2DLerper(float v0_data[], float v1_data[], float v2_data[], float v3_data[], float v4_data[]) {
        // copy data from array pointers to internal arrays
        for (size_t i = 0; i < BUFF_SIZE; i++) {
            _v0_data[i] = v0_data[i];
            _v1_data[i] = v1_data[i];
            _v2_data[i] = v2_data[i];
            _v3_data[i] = v3_data[i];
            _v4_data[i] = v4_data[i];
        } 
    }

    /* Input vector must lie inside the rhombus of vertices (1,0), (0,1), (-1, 0), (0,-1)
    Calculates and stores intepolated data into output_buffer.*/
    void interpolate(float2 input, float* output_buffer) {
        if (!is_in_domain(input)) {input = restrict_input(input);}

        float w1 = abs(input.x);
        float w2 = abs(input.y);
        float w3 = 1.0 - w1 - w2;

        // decides which data buffers to use depending on input
        float* A = (input.y > 0) ? _v1_data : _v3_data;
        float* B = (input.x > 0) ? _v2_data : _v4_data;
        float* C = _v0_data;

        for (size_t i = 0; i < BUFF_SIZE; i++) {
            output_buffer[i] = A[i] * w1 + B[i] * w2 + C[i] * w3;
        } 
    }

    size_t get_buffer_size() const {return BUFF_SIZE;}


};