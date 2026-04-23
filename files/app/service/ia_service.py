"""
Servicio de análisis de IA para entradas del diario
"""

from typing import Dict, Any
import httpx
import os
import re
import json

PALABRAS_CRISIS = [
    "suicidio", "suicidarme", "matarme", "no quiero vivir",
    "mejor muerto", "quitarme la vida", "hacerme daño",
    "cortarme", "autolesion", "no vale la pena seguir"
]

PALABRAS_ANSIEDAD = [
    "ansiedad", "pánico", "angustia", "miedo intenso",
    "no puedo respirar", "ataque de pánico", "taquicardia"
]

PALABRAS_DEPRESION = [
    "depresión", "sin esperanza", "todo es inútil",
    "no me importa nada", "vacío", "no siento nada"
]


async def analizar_entrada_diario(texto: str) -> Dict[str, Any]:
    texto_lower = texto.lower()

    alerta_crisis    = any(p in texto_lower for p in PALABRAS_CRISIS)
    tiene_ansiedad   = any(p in texto_lower for p in PALABRAS_ANSIEDAD)
    tiene_depresion  = any(p in texto_lower for p in PALABRAS_DEPRESION)

    analisis_base = {
        "alerta_crisis": alerta_crisis,
        "temas":         [],
        "sentimiento":   "neutral",
        "intensidad":    0,
        "palabras_clave": [],
    }

    if tiene_ansiedad:
        analisis_base["temas"].append("ansiedad")
    if tiene_depresion:
        analisis_base["temas"].append("tristeza")

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if api_key and len(texto) > 50:
        try:
            analisis_ia = await _analizar_con_claude(texto, api_key)
            analisis_base.update(analisis_ia)
        except Exception:
            pass

    return analisis_base


async def _analizar_con_claude(texto: str, api_key: str) -> Dict[str, Any]:
    prompt = f"""Analiza esta entrada de diario de un estudiante universitario.
Responde SOLO con JSON válido, sin markdown ni explicaciones:

{{
  "sentimiento": "positivo|negativo|neutro|mixto",
  "intensidad": 0,
  "temas": [],
  "palabras_clave": [],
  "resumen_breve": ""
}}

Entrada:
{texto[:500]}"""

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        texto_resp  = resp.json()["content"][0]["text"]
        texto_limpio = re.sub(r"```json|```", "", texto_resp).strip()
        return json.loads(texto_limpio)