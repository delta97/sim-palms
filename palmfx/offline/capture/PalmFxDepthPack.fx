// PalmFxDepthPack.fx : write the raw depth buffer into the image as 24-bit log-encoded RGB.
//
// STATUS: UNTESTED. Written without ReShade or the sim available; it has never been compiled.
// FX-001 and FX-007 must confirm every line marked VERIFY before any capture relies on it.
//
// Written against: ReShade 5.x/6.x API as recalled, exact version not confirmed.
// VERIFY (FX-001): ReShade version in use, and that its MSFS 2024 depth access works
//   (reversed-Z, near/far, logarithmic vs linear depth, buffer format, multiplayer lockout).
//
// Encoding "log24" (arithmetic only, no integer intrinsics). Raw depth d as read:
//   v = d < DMIN ? 0 : round((ln d - ln DMIN) / (-ln DMIN) * 16777215)
//   R = floor(v / 65536), G = floor(fmod(v, 65536) / 256), B = fmod(v, 256), A = 255
//   output = float4(R, G, B, 255) / 255
// Decode (palmfx/offline/depth.py unpack_log24):
//   v = R * 65536 + G * 256 + B
//   d = v == 0 ? 0 : exp(ln DMIN + v / 16777215 * (-ln DMIN))     (d = 0 means sky / below DMIN)
// DMIN must equal palmfx/offline/depth.py DMIN (1e-7). round(x) is floor(x + 0.5).
//
// Use: enable this effect ALONE (no other effects; they would alter the packed pixels), with
// ReShade screenshots saving before and after (the "before" image is the clean colour frame).
// VERIFY (FX-007): the backbuffer is 8-bit UNORM and not sRGB-converted on write, otherwise
//   the bytes will not survive; compare decoded depth against DisplayDepth.fx.

#include "ReShade.fxh"

// Pack constant. Keep in sync with depth.py. Uniform so it shows in the overlay; do not change.
uniform float DMIN = 1e-7;

float3 PackLog24(float d)
{
    float v = 0.0;
    if (d >= DMIN)
    {
        float t = (log(d) - log(DMIN)) / (-log(DMIN));
        v = floor(t * 16777215.0 + 0.5);
    }
    float r = floor(v / 65536.0);
    float g = floor(fmod(v, 65536.0) / 256.0);
    float b = fmod(v, 256.0);
    return float3(r, g, b);
}

float4 PS_PackDepth(float4 pos : SV_Position, float2 uv : TEXCOORD) : SV_Target
{
    // VERIFY (FX-001/FX-007): ReShade::DepthBuffer is the raw (non-linearised) depth sampler in
    // ReShade.fxh. If only ReShade::GetLinearizedDepth(uv) is available, use it instead and
    // record depth_encoding.source = "linearized" in session.json.
    // VERIFY: the sampled value is in (0, 1] and which direction (reversed-Z) it runs; the
    // packing does not depend on direction, but the later depth-model fit does.
    float d = tex2Dlod(ReShade::DepthBuffer, float4(uv, 0.0, 0.0)).x;
    return float4(PackLog24(d), 255.0) / 255.0;
}

technique PalmFxDepthPack
{
    pass Pack
    {
        VertexShader = PostProcessVS;
        PixelShader = PS_PackDepth;
    }
}
