# Google OAuth Troubleshooting

Реальные проблемы, с которыми столкнулись при настройке Google OAuth для Hermes.

## USB Security Key Prompt (Advanced Protection)

### Симптом
При попытке авторизации через OAuth (шаг 3 — открытие auth URL в браузере) Google показывает окно:
- Требует вставить USB-ключ безопасности
- Нет альтернативных способов подтверждения (нет «Try another way»)
- Без физического ключа авторизация невозможна

### Причина
Google Advanced Protection Program (APP) включена на аккаунте. APP требует ТОЛЬКО физический ключ безопасности (Titan, Feitan) — никакие другие методы 2FA не принимаются.

### Решения (в порядке предпочтения)

1. **Отдельный Google-аккаунт для OAuth**
   - Создать новый Google-аккаунт БЕЗ Advanced Protection
   - Использовать его только для Google Drive API
   - Расшарить папку синхронизации на этот аккаунт (роль Writer)

2. **API Key вместо OAuth**
   - Google Drive API поддерживает API keys для публичных данных
   - Для приватных данных — не подходит
   - https://console.cloud.google.com/apis/credentials → Create API Key

3. **Отключить Advanced Protection (не рекомендуется)**
   - https://myaccount.google.com/advanced-protection
   - Требует наличия ключа для отключения (замкнутый круг)

4. **Google Cloud Console OAuth Consent Screen**
   - Даже без APP, на странице OAuth consent screen могут быть дополнительные проверки
   - Убедиться что: User Type = External, Publishing Status = Testing, тестовые пользователи добавлены

## Vision Tool Not Appearing After Enable

### Симптом
`hermes tools enable vision` → `✓ Enabled: vision`
`hermes tools list` → показывает `vision` как enabled
После `/reset` → `vision_analyze` всё ещё отсутствует в списке инструментов

### Обходные пути для чтения скриншотов
1. **Не работает:** PIL + pytesseract без tesseract binary на Windows
2. **Не работает:** `browser_navigate` + `browser_snapshot` на .png — snapshot пустой
3. **Работает:** если есть tesseract: `winget install tesseract` → `uv pip install pytesseract pillow` → OCR
4. **Лучший вариант:** попросить пользователя описать окно текстом (самый быстрый fallback)

## Связанные заметки
- Скилл `google-workspace` содержит полную процедуру OAuth-настройки
- Папка синхронизации: `14z50C-o27hUrWWDrOVCGqzc9sPtkv_dB`