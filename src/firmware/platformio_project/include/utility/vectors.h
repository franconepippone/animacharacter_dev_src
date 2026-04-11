#pragma once
#include <Arduino.h>

template <typename T = float>
class vec2 {
public:
    T x;
    T y;

    vec2() : x(T()), y(T()) {};
    vec2(T x) : x(x), y(x) {};
    vec2(T x, T y) : x(x), y(y) {};
    template <typename G>
    vec2(vec2<G> a) : x((T)a.x), y((T)a.y) {};
    template <typename G>
    vec2(vec2<G>* a) : x((T)a->x), y((T)a->y) {};

    T* get_array() {return &x;}
};

typedef vec2<float> float2;
typedef vec2<int> int2;
