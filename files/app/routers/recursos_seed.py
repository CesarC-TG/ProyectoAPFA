"""
Script de seed para poblar la tabla recursos con contenido real.
Ejecutar una vez: python recursos_seed.py
Desde la raíz del proyecto: python -m app.recursos_seed
"""
import asyncio, sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.models import Recurso, TipoRecurso

RECURSOS = [
    # ── RESPIRACIÓN ─────────────────────────────────────
    {
        "titulo": "Respiración 4-7-8 para la ansiedad",
        "descripcion": "Técnica clínica de relajación: inhala 4 s, retén 7 s, exhala 8 s. Reduce el cortisol y calma el sistema nervioso en menos de 2 minutos.",
        "tipo": TipoRecurso.RESPIRACION,
        "duracion_minutos": 3,
        "contenido": {
            "pasos": [
                "Siéntate con la espalda recta y cierra los ojos.",
                "Exhala completamente por la boca con un sonido suave.",
                "Cierra la boca e inhala en silencio por la nariz contando hasta 4.",
                "Contén la respiración contando hasta 7.",
                "Exhala por la boca completamente contando hasta 8.",
                "Repite el ciclo 3 veces más (4 ciclos en total)."
            ],
            "beneficios": ["Reduce ansiedad", "Mejora el sueño", "Baja la presión arterial"],
            "emoji_pasos": ["🪑", "💨", "👃", "⏸️", "💨", "🔄"]
        },
        "orden": 1,
    },
    {
        "titulo": "Respiración diafragmática",
        "descripcion": "Activa el nervio vago y el sistema parasimpático. Ideal antes de exámenes o situaciones de estrés académico.",
        "tipo": TipoRecurso.RESPIRACION,
        "duracion_minutos": 5,
        "contenido": {
            "pasos": [
                "Acuéstate o siéntate cómodamente.",
                "Coloca una mano en el pecho y otra en el abdomen.",
                "Inhala lentamente por la nariz, sintiendo que el abdomen se expande (no el pecho).",
                "Exhala lentamente por la boca, hundiendo suavemente el abdomen.",
                "Repite durante 5 minutos."
            ],
            "beneficios": ["Reduce el estrés", "Mejora la concentración", "Alivia tensión muscular"],
        },
        "orden": 2,
    },
    {
        "titulo": "Técnica Box Breathing (Cuadrada)",
        "descripcion": "Usada por militares y atletas de élite para calmarse rápido. 4 lados iguales: inhala, retén, exhala, retén.",
        "tipo": TipoRecurso.RESPIRACION,
        "duracion_minutos": 4,
        "contenido": {
            "pasos": [
                "Exhala todo el aire de tus pulmones.",
                "Inhala por la nariz contando 4 segundos.",
                "Retén el aire contando 4 segundos.",
                "Exhala por la boca contando 4 segundos.",
                "Retén sin inhalar contando 4 segundos.",
                "Repite 4 veces o hasta sentirte calmado/a."
            ],
            "beneficios": ["Control inmediato de pánico", "Mejora foco", "Regula emociones"]
        },
        "orden": 3,
    },
    # ── MEDITACIÓN ───────────────────────────────────────
    {
        "titulo": "Escaneo corporal de 5 minutos",
        "descripcion": "Meditación guiada para liberar tensión física. Recorre mentalmente tu cuerpo de pies a cabeza notando sensaciones sin juzgar.",
        "tipo": TipoRecurso.MEDITACION,
        "duracion_minutos": 5,
        "contenido": {
            "pasos": [
                "Cierra los ojos y respira profundamente 3 veces.",
                "Lleva tu atención a los pies: ¿sientes calor, frío, tensión?",
                "Sube lentamente: tobillos, pantorrillas, rodillas, muslos.",
                "Continúa: abdomen, pecho, espalda, hombros.",
                "Termina en cuello, mandíbula, frente y cuero cabelludo.",
                "Abre los ojos lentamente y mueve los dedos."
            ],
            "beneficios": ["Reduce tensión muscular", "Mejora conciencia corporal", "Disminuye ansiedad"]
        },
        "orden": 4,
    },
    {
        "titulo": "Meditación mindfulness de 10 minutos",
        "descripcion": "Práctica de atención plena para anclar la mente al presente. Sin experiencia previa necesaria.",
        "tipo": TipoRecurso.MEDITACION,
        "duracion_minutos": 10,
        "contenido": {
            "pasos": [
                "Siéntate cómodo/a, espalda recta, manos sobre los muslos.",
                "Cierra los ojos o baja la mirada.",
                "Enfoca toda tu atención en la respiración natural.",
                "Cuando tu mente divague (y lo hará), simplemente vuelve a la respiración sin juzgarte.",
                "Observa los pensamientos como nubes que pasan, sin engancharte.",
                "Al terminar, toma 3 respiraciones profundas y abre los ojos."
            ],
            "beneficios": ["Reduce rumiación", "Mejora regulación emocional", "Aumenta concentración"]
        },
        "orden": 5,
    },
    {
        "titulo": "Visualización del lugar seguro",
        "descripcion": "Técnica de imaginación guiada para crear un espacio mental de calma. Muy útil en momentos de agobio o crisis emocional.",
        "tipo": TipoRecurso.MEDITACION,
        "duracion_minutos": 8,
        "contenido": {
            "pasos": [
                "Cierra los ojos y respira profundo.",
                "Imagina un lugar donde te sientas completamente seguro/a (real o imaginario).",
                "Activa todos los sentidos: ¿qué ves, escuchas, hueles, sientes en la piel?",
                "Quédate ahí 5 minutos, explorando cada detalle.",
                "Recuerda que puedes volver a este lugar mental cuando lo necesites.",
                "Regresa lentamente al presente."
            ],
            "beneficios": ["Calma crisis emocionales", "Reduce disociación", "Crea ancla de seguridad"]
        },
        "orden": 6,
    },
    # ── EJERCICIO ────────────────────────────────────────
    {
        "titulo": "Rutina anti-estrés de 7 minutos",
        "descripcion": "Ejercicios físicos de alta eficiencia para liberar cortisol y endorfinas. Sin equipo, en cualquier espacio.",
        "tipo": TipoRecurso.EJERCICIO,
        "duracion_minutos": 7,
        "contenido": {
            "ejercicios": [
                {"nombre": "Saltos de tijera", "duracion": "30 s", "descanso": "10 s"},
                {"nombre": "Sentadillas", "duracion": "30 s", "descanso": "10 s"},
                {"nombre": "Flexiones (o rodillas al piso)", "duracion": "30 s", "descanso": "10 s"},
                {"nombre": "Abdominales", "duracion": "30 s", "descanso": "10 s"},
                {"nombre": "Trote en el lugar", "duracion": "30 s", "descanso": "10 s"},
                {"nombre": "Estiramiento completo", "duracion": "60 s", "descanso": "0 s"}
            ],
            "beneficios": ["Libera endorfinas", "Reduce cortisol", "Mejora estado de ánimo en minutos"]
        },
        "orden": 7,
    },
    {
        "titulo": "Yoga restaurativo para ansiedad",
        "descripcion": "Secuencia suave de posturas para calmar el sistema nervioso. Ideal para practicar antes de dormir o en momentos de mucho estrés.",
        "tipo": TipoRecurso.EJERCICIO,
        "duracion_minutos": 15,
        "url_externo": "https://www.youtube.com/results?search_query=yoga+restaurativo+ansiedad+español",
        "contenido": {
            "posturas": [
                {"nombre": "Niño (Balasana)", "tiempo": "2 min"},
                {"nombre": "Piernas contra la pared (Viparita Karani)", "tiempo": "3 min"},
                {"nombre": "Torsión supina", "tiempo": "2 min cada lado"},
                {"nombre": "Savasana", "tiempo": "5 min"}
            ],
            "beneficios": ["Activa sistema parasimpático", "Reduce insomnio", "Alivia tensión lumbar"]
        },
        "orden": 8,
    },
    {
        "titulo": "Caminata mindful de 10 minutos",
        "descripcion": "Transforma una caminata normal en práctica de atención plena. No necesitas ir a ningún lado especial, funciona en cualquier lugar.",
        "tipo": TipoRecurso.EJERCICIO,
        "duracion_minutos": 10,
        "contenido": {
            "pasos": [
                "Camina a ritmo normal, sin destino urgente.",
                "Nota el contacto de cada pie con el suelo.",
                "Observa 5 cosas que puedes VER a tu alrededor.",
                "Escucha 4 sonidos distintos.",
                "Siente 3 texturas o sensaciones físicas.",
                "Huele 2 aromas en el ambiente.",
                "Saborea 1 cosa (una bebida, un dulce, o simplemente el aire)."
            ],
            "beneficios": ["Interrumpe rumiación", "Regresa al presente", "Combina ejercicio y mindfulness"]
        },
        "orden": 9,
    },
    # ── LECTURA ──────────────────────────────────────────
    {
        "titulo": "¿Qué es la ansiedad y cómo funciona?",
        "descripcion": "Guía clara y sin tecnicismos sobre el mecanismo de la ansiedad en el cerebro, por qué aparece y qué la mantiene activa.",
        "tipo": TipoRecurso.LECTURA,
        "duracion_minutos": 8,
        "contenido": {
            "secciones": [
                {
                    "titulo": "La ansiedad es una alarma, no una debilidad",
                    "texto": "La ansiedad es la respuesta natural del cerebro ante una amenaza percibida. La amígdala activa el eje HPA y libera adrenalina y cortisol. El problema no es la alarma, sino cuando se dispara sin amenaza real."
                },
                {
                    "titulo": "El ciclo de la ansiedad",
                    "texto": "Pensamiento amenazante → Activación fisiológica → Interpretación catastrófica → Más activación. La evitación a corto plazo lo mantiene a largo plazo."
                },
                {
                    "titulo": "Qué realmente ayuda",
                    "texto": "Exposición gradual, reestructuración cognitiva, técnicas de regulación del sistema nervioso (respiración, ejercicio), y apoyo profesional cuando interfiere con la vida diaria."
                }
            ],
            "cita": "La ansiedad no es un defecto de carácter, es el precio de tener imaginación."
        },
        "orden": 10,
    },
    {
        "titulo": "Cómo hablar con alguien que está pasándola mal",
        "descripcion": "Guía práctica para acompañar a un amigo o familiar en crisis emocional sin decir las frases que (aunque bien intencionadas) duelen.",
        "tipo": TipoRecurso.LECTURA,
        "duracion_minutos": 6,
        "contenido": {
            "secciones": [
                {
                    "titulo": "Lo que SÍ funciona",
                    "texto": "Escuchar sin interrumpir. Validar sin minimizar ('entiendo que eso duele mucho'). Preguntar '¿cómo puedo ayudarte?' en lugar de asumir."
                },
                {
                    "titulo": "Frases que evitar",
                    "texto": "'Todo pasa por algo', 'Hay gente peor', 'Anímate', 'No es para tanto'. Estas frases invalidan la experiencia y generan distanciamiento."
                },
                {
                    "titulo": "Cuándo buscar ayuda profesional",
                    "texto": "Si menciona hacerse daño, si lleva más de 2 semanas sin poder funcionar con normalidad, o si tú te sientes rebasado/a. No tienes que cargar solo/a con eso."
                }
            ]
        },
        "orden": 11,
    },
    {
        "titulo": "Higiene del sueño para estudiantes",
        "descripcion": "El sueño deficiente amplifica el estrés, deteriora la memoria y dispara la ansiedad. Guía basada en evidencia para mejorar tu descanso.",
        "tipo": TipoRecurso.LECTURA,
        "duracion_minutos": 7,
        "contenido": {
            "secciones": [
                {
                    "titulo": "Por qué el sueño importa tanto",
                    "texto": "Durante el sueño profundo, el cerebro consolida la memoria, regula las emociones y repara tejidos. Dormir menos de 7 horas afecta el rendimiento académico tanto como el alcohol."
                },
                {
                    "titulo": "10 hábitos de higiene del sueño",
                    "texto": "1) Horario fijo de sueño. 2) Sin pantallas 1 h antes. 3) Cuarto oscuro y fresco. 4) Sin cafeína después de las 2 pm. 5) Actividad física diaria (no nocturna). 6) Rutina relajante previa. 7) Cama solo para dormir. 8) No ver el reloj si te despiertas. 9) Limitar siestas a 20 min. 10) Exponerse a luz solar en la mañana."
                }
            ]
        },
        "orden": 12,
    },
    # ── VIDEO ─────────────────────────────────────────────
    {
        "titulo": "TED Talk: El poder de la vulnerabilidad",
        "descripcion": "Brené Brown explica por qué la vergüenza y el miedo al rechazo nos impiden vivir plenamente, y cómo la vulnerabilidad es en realidad nuestra mayor fortaleza.",
        "tipo": TipoRecurso.VIDEO,
        "duracion_minutos": 20,
        "url_externo": "https://www.ted.com/talks/brene_brown_the_power_of_vulnerability",
        "contenido": {
            "subtitulos": "Disponible en español",
            "plataforma": "TED.com",
            "puntos_clave": [
                "La vergüenza es universal, pero no hablar de ella la alimenta.",
                "Las personas con mayor bienestar no evitan la vulnerabilidad, la abrazan.",
                "La conexión auténtica requiere ser visto tal como eres."
            ]
        },
        "orden": 13,
    },
    {
        "titulo": "Cómo controlar el estrés antes de un examen",
        "descripcion": "Técnicas prácticas de neurociencia para manejar la ansiedad ante evaluaciones. Aplicable la noche anterior y el día del examen.",
        "tipo": TipoRecurso.VIDEO,
        "duracion_minutos": 12,
        "url_externo": "https://www.youtube.com/results?search_query=controlar+ansiedad+examen+tecnicas",
        "contenido": {
            "temas": [
                "Reencuadre de la activación (el estrés como aliado)",
                "Técnica de escritura expresiva pre-examen",
                "Respiración de emergencia en el aula",
                "Postura corporal y su efecto en la confianza"
            ]
        },
        "orden": 14,
    },
    # ── CLÍNICA FES ACATLÁN ───────────────────────────────
    {
        "titulo": "Clínica de Salud Mental — FES Acatlán",
        "descripcion": "Servicio de atención psicológica gratuito para estudiantes de la FES Acatlán. Citas con psicólogos profesionales de la UNAM.",
        "tipo": TipoRecurso.CLINICA,
        "telefono": "55 5623-1666",
        "direccion": "Edificio D, Planta Baja — FES Acatlán, Santa Cruz Acatlán, Naucalpan, Edo. de México",
        "horario": "Lunes a Viernes 8:00–19:00 h",
        "disponible_24h": False,
        "contenido": {
            "servicios": [
                "Psicoterapia individual",
                "Orientación vocacional",
                "Intervención en crisis",
                "Grupos de apoyo"
            ],
            "requisitos": "Credencial vigente de la UNAM. Cita previa o primera consulta sin cita.",
            "costo": "Gratuito para estudiantes activos"
        },
        "orden": 15,
    },
    {
        "titulo": "Centro de Servicios Psicológicos — UNAM",
        "descripcion": "Atención psicológica de la Facultad de Psicología UNAM. Bajas cuotas diferenciadas y opciones gratuitas.",
        "tipo": TipoRecurso.CLINICA,
        "telefono": "55 5622-2300",
        "direccion": "Av. Universidad 3004, Edificio de Posgrado, CU, Coyoacán, CDMX",
        "horario": "Lunes a Viernes 8:00–20:00 h",
        "disponible_24h": False,
        "contenido": {
            "servicios": ["Psicoterapia individual", "Terapia de pareja", "Terapia infantil", "Neuropsicología"],
            "costo": "Cuotas desde $50 MXN según estudio socioeconómico"
        },
        "orden": 16,
    },
    # ── LÍNEAS DE CRISIS ──────────────────────────────────
    {
        "titulo": "SAPTEL — Línea de Crisis 24/7",
        "descripcion": "Sistema de Atención Psicológica por Teléfono. Apoyo emocional gratuito las 24 horas del día, los 365 días del año.",
        "tipo": TipoRecurso.LINEA_CRISIS,
        "telefono": "800-290-0024",
        "disponible_24h": True,
        "contenido": {
            "tipo_apoyo": "Crisis, duelo, ansiedad, depresión, ideación suicida",
            "idiomas": ["Español"],
            "costo": "Gratuito desde cualquier teléfono"
        },
        "orden": 17,
    },
    {
        "titulo": "IMSS — Orientación Salud Mental",
        "descripcion": "Línea de orientación en crisis de salud mental del IMSS. Atención de urgencias psiquiátricas.",
        "tipo": TipoRecurso.LINEA_CRISIS,
        "telefono": "800 911 2000",
        "disponible_24h": True,
        "contenido": {
            "tipo_apoyo": "Urgencias psiquiátricas, orientación en crisis",
            "costo": "Gratuito"
        },
        "orden": 18,
    },
    {
        "titulo": "LOCATEL — Información y Apoyo CDMX",
        "descripcion": "Servicio de información ciudadana del Gobierno de la CDMX. Orientación a servicios de salud mental en la ciudad.",
        "tipo": TipoRecurso.LINEA_CRISIS,
        "telefono": "55 5658-1111",
        "disponible_24h": True,
        "contenido": {
            "tipo_apoyo": "Orientación a servicios de salud, información ciudadana",
            "costo": "Gratuito"
        },
        "orden": 19,
    },
]

async def seed():
    async with AsyncSessionLocal() as db:
        # Verificar si ya hay recursos
        from sqlalchemy import select, func
        count = (await db.execute(select(func.count()).select_from(Recurso))).scalar()
        if count > 0:
            print(f"Ya existen {count} recursos. Si quieres recargar, elimina los existentes primero.")
            return

        for data in RECURSOS:
            r = Recurso(
                id               = str(uuid.uuid4()),
                titulo           = data["titulo"],
                descripcion      = data.get("descripcion"),
                tipo             = data["tipo"],
                contenido        = data.get("contenido"),
                duracion_minutos = data.get("duracion_minutos"),
                imagen_url       = data.get("imagen_url"),
                url_externo      = data.get("url_externo"),
                telefono         = data.get("telefono"),
                direccion        = data.get("direccion"),
                horario          = data.get("horario"),
                disponible_24h   = data.get("disponible_24h", False),
                orden            = data.get("orden", 99),
                activo           = True,
            )
            db.add(r)

        await db.commit()
        print(f"✅ {len(RECURSOS)} recursos creados correctamente.")

if __name__ == "__main__":
    asyncio.run(seed())