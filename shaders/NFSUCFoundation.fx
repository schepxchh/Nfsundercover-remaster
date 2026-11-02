// NFS Undercover: Definitive Remaster — Visual Foundation 0.2
// SPDX-License-Identifier: MIT
// SDR, display-referred post-processing. No depth access or engine hooks.
// Syntax reference: crosire/reshade-shaders REFERENCE.md (slim), 2026-11-02.
// Fullscreen-triangle convention follows ReShade.fxh (CC0-1.0).
#if !defined(__RESHADE__) || __RESHADE__ < 60000
    #error "NFSUC Foundation targets ReShade 6.0 or newer."
#endif

uniform float ExposureEV <
    ui_type = "slider"; ui_label = "Exposure (EV)";
    ui_min = -0.50; ui_max = 0.50; ui_step = 0.01;
    ui_tooltip = "Small display-referred exposure adjustment; cannot recover clipped game highlights.";
> = 0.03;
uniform float LightContrast <
    ui_type = "slider"; ui_label = "Light contrast";
    ui_min = 0.00; ui_max = 0.20; ui_step = 0.005;
    ui_tooltip = "Luminance contrast around linear 0.18. Lower if road shadows become hard to read.";
> = 0.035;
uniform float Saturation <
    ui_type = "slider"; ui_label = "Saturation";
    ui_min = 0.80; ui_max = 1.15; ui_step = 0.005;
> = 1.025;
uniform float Warmth <
    ui_type = "slider"; ui_label = "Warmth";
    ui_min = -0.50; ui_max = 0.50; ui_step = 0.01;
    ui_tooltip = "Subtle RGB balance, not physical color-temperature correction.";
> = 0.06;
uniform float ShadowLift <
    ui_type = "slider"; ui_label = "Shadow readability";
    ui_min = 0.00; ui_max = 0.015; ui_step = 0.0005;
    ui_tooltip = "Small linear-light lift in dark values, tapered to preserve exact black and white.";
> = 0.001;
uniform float HighlightCompression <
    ui_type = "slider"; ui_label = "Highlight shoulder";
    ui_min = 0.00; ui_max = 0.50; ui_step = 0.01;
    ui_tooltip = "Smooth peak compression above linear 0.65; cannot restore missing source detail.";
> = 0.15;
uniform float EffectStrength <
    ui_type = "slider"; ui_label = "Grade strength";
    ui_min = 0.00; ui_max = 1.00; ui_step = 0.01;
> = 1.00;
uniform float BloomStrength <
    ui_type = "slider"; ui_label = "Bloom strength";
    ui_min = 0.00; ui_max = 0.15; ui_step = 0.005;
    ui_tooltip = "Optional screen-space highlight spread. Toggle the Bloom technique off to remove its GPU cost.";
> = 0.035;
uniform float BloomThreshold <
    ui_type = "slider"; ui_label = "Bloom threshold (linear)";
    ui_min = 0.35; ui_max = 0.90; ui_step = 0.01;
> = 0.65;
uniform float BloomRadius <
    ui_type = "slider"; ui_label = "Bloom radius";
    ui_min = 0.50; ui_max = 2.00; ui_step = 0.05;
    ui_tooltip = "Radius scales with image height; same physical pixel radius on both axes.";
> = 1.00;

texture NFSUC_Color : COLOR;
sampler NFSUC_Input { Texture = NFSUC_Color; SRGBTexture = false; };

// Quarter-resolution linear-light buffers. No external textures or includes.
texture NFSUC_Bright {
    Width = BUFFER_WIDTH / 4; Height = BUFFER_HEIGHT / 4;
    Format = RGBA16F;
};
texture NFSUC_Horizontal {
    Width = BUFFER_WIDTH / 4; Height = BUFFER_HEIGHT / 4;
    Format = RGBA16F;
};
texture NFSUC_Blurred {
    Width = BUFFER_WIDTH / 4; Height = BUFFER_HEIGHT / 4;
    Format = RGBA16F;
};
sampler NFSUC_BrightSampler { Texture = NFSUC_Bright; AddressU = CLAMP; AddressV = CLAMP; };
sampler NFSUC_HorizontalSampler { Texture = NFSUC_Horizontal; AddressU = CLAMP; AddressV = CLAMP; };
sampler NFSUC_BlurredSampler { Texture = NFSUC_Blurred; AddressU = CLAMP; AddressV = CLAMP; };

void NFSUC_VS(uint vertex : SV_VertexID,
    out float4 position : SV_Position, out float2 uv : TEXCOORD)
{
    uv = float2(vertex == 2 ? 2.0 : 0.0, vertex == 1 ? 2.0 : 0.0);
    position = float4(uv * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}

float3 NFSUC_Decode(float3 c) { return pow(saturate(c), 2.2); }
float3 NFSUC_Encode(float3 c) { return pow(saturate(c), 1.0 / 2.2); }
float NFSUC_Luma(float3 c) { return dot(c, float3(0.2126, 0.7152, 0.0722)); }

float4 NFSUC_GradePS(float4 position : SV_Position, float2 uv : TEXCOORD) : SV_Target
{
    float4 source = tex2D(NFSUC_Input, uv);
    float3 c = NFSUC_Decode(source.rgb) * exp2(ExposureEV);
    float y = NFSUC_Luma(c);
    // Contrast acts on luminance only, preserving channel ratios.
    c *= pow((y + 0.02) / 0.20, LightContrast);
    y = saturate(NFSUC_Luma(c));
    c += ShadowLift * 4.0 * sqrt(y) * pow(1.0 - y, 4.0);
    c *= float3(1.0 + 0.08 * Warmth, 1.0, 1.0 - 0.08 * Warmth);
    y = NFSUC_Luma(c);
    c = max(lerp(float3(y, y, y), c, Saturation), 0.0);
    // A monotone rational shoulder, with matching slope at the knee.
    // Scaling the triplet by its peak avoids independent RGB clipping.
    float peak = max(c.r, max(c.g, c.b));
    float t = max(peak - 0.65, 0.0) / 0.35;
    float compressed = 0.65 + 0.35 * t / (1.0 + HighlightCompression * t);
    // Express as a reduction so values below the knee retain unit gain,
    // including near-black values smaller than the division guard.
    c *= 1.0 - (peak - min(peak, compressed)) / max(peak, 0.000001);
    // Final hue-preserving gamut scale if exposure still exceeds SDR white.
    c /= max(1.0, max(c.r, max(c.g, c.b)));
    return float4(lerp(source.rgb, NFSUC_Encode(c), EffectStrength), source.a);
}

float3 NFSUC_Extract(float2 uv)
{
    float3 c = NFSUC_Decode(tex2D(NFSUC_Input, uv).rgb);
    float peak = max(c.r, max(c.g, c.b));
    // Smooth threshold; bounded input and non-negative weights prevent ringing.
    return c * smoothstep(BloomThreshold, min(BloomThreshold + 0.15, 1.0), peak);
}

float4 NFSUC_PrefilterPS(float4 position : SV_Position, float2 uv : TEXCOORD) : SV_Target
{
    float2 p = float2(BUFFER_RCP_WIDTH, BUFFER_RCP_HEIGHT);
    float3 bright = NFSUC_Extract(uv + p * float2(-1.0, -1.0));
    bright += NFSUC_Extract(uv + p * float2(1.0, -1.0));
    bright += NFSUC_Extract(uv + p * float2(-1.0, 1.0));
    bright += NFSUC_Extract(uv + p * float2(1.0, 1.0));
    return float4(bright * 0.25, 1.0);
}

// Positive, normalized 9-tap separable kernel. Radius normalized to 1440p.
float4 NFSUC_BlurHPS(float4 position : SV_Position, float2 uv : TEXCOORD) : SV_Target
{
    float2 d = float2(4.0 * BUFFER_RCP_WIDTH, 0.0) * BloomRadius * (BUFFER_HEIGHT / 1440.0);
    float3 c = tex2D(NFSUC_BrightSampler, uv).rgb * 0.2270270270;
    c += (tex2D(NFSUC_BrightSampler, uv + d).rgb + tex2D(NFSUC_BrightSampler, uv - d).rgb) * 0.1945945946;
    c += (tex2D(NFSUC_BrightSampler, uv + d * 2.0).rgb + tex2D(NFSUC_BrightSampler, uv - d * 2.0).rgb) * 0.1216216216;
    c += (tex2D(NFSUC_BrightSampler, uv + d * 3.0).rgb + tex2D(NFSUC_BrightSampler, uv - d * 3.0).rgb) * 0.0540540541;
    c += (tex2D(NFSUC_BrightSampler, uv + d * 4.0).rgb + tex2D(NFSUC_BrightSampler, uv - d * 4.0).rgb) * 0.0162162162;
    return float4(c, 1.0);
}
float4 NFSUC_BlurVPS(float4 position : SV_Position, float2 uv : TEXCOORD) : SV_Target
{
    float2 d = float2(0.0, 4.0 * BUFFER_RCP_HEIGHT) * BloomRadius * (BUFFER_HEIGHT / 1440.0);
    float3 c = tex2D(NFSUC_HorizontalSampler, uv).rgb * 0.2270270270;
    c += (tex2D(NFSUC_HorizontalSampler, uv + d).rgb + tex2D(NFSUC_HorizontalSampler, uv - d).rgb) * 0.1945945946;
    c += (tex2D(NFSUC_HorizontalSampler, uv + d * 2.0).rgb + tex2D(NFSUC_HorizontalSampler, uv - d * 2.0).rgb) * 0.1216216216;
    c += (tex2D(NFSUC_HorizontalSampler, uv + d * 3.0).rgb + tex2D(NFSUC_HorizontalSampler, uv - d * 3.0).rgb) * 0.0540540541;
    c += (tex2D(NFSUC_HorizontalSampler, uv + d * 4.0).rgb + tex2D(NFSUC_HorizontalSampler, uv - d * 4.0).rgb) * 0.0162162162;
    return float4(c, 1.0);
}
float4 NFSUC_BloomPS(float4 position : SV_Position, float2 uv : TEXCOORD) : SV_Target
{
    float4 source = tex2D(NFSUC_Input, uv);
    float3 base = NFSUC_Decode(source.rgb);
    float3 glow = saturate(tex2D(NFSUC_BlurredSampler, uv).rgb * BloomStrength);
    // Bounded screen blend in approximate linear light.
    return float4(NFSUC_Encode(1.0 - (1.0 - base) * (1.0 - glow)), source.a);
}

technique NFSUC_Grade < ui_label = "NFSUC | Foundation grade"; ui_tooltip = "SDR color, light contrast and highlight shoulder. Also affects HUD and menus."; >
{
    pass Grade { VertexShader = NFSUC_VS; PixelShader = NFSUC_GradePS; SRGBWriteEnable = false; }
}
technique NFSUC_Bloom < ui_label = "NFSUC | Restrained bloom"; ui_tooltip = "Optional quarter-resolution screen-space light spread. No volumetrics, GI or ray tracing."; >
{
    pass Prefilter { VertexShader = NFSUC_VS; PixelShader = NFSUC_PrefilterPS; RenderTarget = NFSUC_Bright; }
    pass Horizontal { VertexShader = NFSUC_VS; PixelShader = NFSUC_BlurHPS; RenderTarget = NFSUC_Horizontal; }
    pass Vertical { VertexShader = NFSUC_VS; PixelShader = NFSUC_BlurVPS; RenderTarget = NFSUC_Blurred; }
    pass Composite { VertexShader = NFSUC_VS; PixelShader = NFSUC_BloomPS; SRGBWriteEnable = false; }
}
