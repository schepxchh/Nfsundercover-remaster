// SPDX-License-Identifier: MIT
// Native DX9 ps_3_0 SDR grade. Own implementation; no ReShadeFX dependencies.
sampler2D Color : register(s0);
float4 GradeA : register(c0); // exposure EV, contrast, saturation, warmth
float4 GradeB : register(c1); // shoulder, strength, reserved, reserved
float4 main(float2 uv : TEXCOORD0) : COLOR0
{
    float4 src = tex2D(Color, uv);
    float3 c = pow(saturate(src.rgb), 2.2) * exp2(GradeA.x);
    float y = dot(c, float3(0.2126, 0.7152, 0.0722));
    c *= pow((y + 0.02) / 0.20, GradeA.y);
    c *= float3(1.0 + 0.08 * GradeA.w, 1.0, 1.0 - 0.08 * GradeA.w);
    y = dot(c, float3(0.2126, 0.7152, 0.0722));
    c = max(lerp(float3(y,y,y), c, GradeA.z), 0.0);
    float peak = max(c.r, max(c.g, c.b));
    float t = max(peak - 0.65, 0.0) / 0.35;
    float shoulder = 0.65 + 0.35 * t / (1.0 + GradeB.x * t);
    c *= 1.0 - (peak - min(peak, shoulder)) / max(peak, 0.000001);
    c /= max(1.0, max(c.r, max(c.g, c.b)));
    return float4(lerp(src.rgb, pow(saturate(c), 1.0/2.2), GradeB.y), src.a);
}
