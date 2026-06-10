from __future__ import annotations

import asyncio

from core.config import get_settings
from db.queries import add_template, list_templates
from db.session import create_engine, create_session_factory

TEMPLATES = [
    ("thailand", "relocation", "По Таиланду лучше заранее проверить район, визу и бюджет на первые месяцы. Если нужно, можно написать в личку, подскажу по шагам 🙏"),
    ("thailand", "realty", "По жилью в Таиланде сильно решает район и срок договора. Если хотите, можно написать в личку, помогу понять, где смотреть варианты."),
    ("bali", "relocation", "На Бали важно заранее проверить визу, район и условия аренды. Если нужно быстро сориентироваться, можно написать в личку 🌴"),
    ("vietnam", "relocation", "По Вьетнаму лучше заранее уточнить визу, район и формат проживания. Если есть вопросы, можно написать в личку, подскажу 🇻🇳"),
]


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        existing = await list_templates(session)
        if existing:
            print(f"Templates already exist: {len(existing)}")
            return
        for geo, category, text in TEMPLATES:
            await add_template(session, geo, category, text)
            print(f"Added template: {geo}/{category}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
