# Verifies the Gemini API key actually works. Run from the project root:
#     .\check-key.ps1
Set-Location "$PSScriptRoot\backend"
& ".venv\Scripts\python.exe" -c @"
import warnings; warnings.filterwarnings('ignore')
from app.config import get_settings
s = get_settings()
if not s.google_api_key:
    print('NO KEY set in backend/.env'); raise SystemExit(1)
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    m = ChatGoogleGenerativeAI(model=s.google_chat_model, google_api_key=s.google_api_key,
                               temperature=0, max_output_tokens=32, timeout=30)
    r = m.invoke('Reply with exactly: OK')
    print('KEY WORKS  ->', repr(getattr(r, 'content', r))[:60])
    print('Restart the backend and answers will be generative.')
except Exception as e:
    msg = str(e)
    if 'API_KEY_SERVICE_BLOCKED' in msg:
        print('BLOCKED    -> the key restriction excludes the Generative Language API.')
        print('             Fix: console.cloud.google.com/apis/credentials -> your key')
        print('             -> API restrictions -> Do not restrict key -> Save')
    elif 'API_KEY_INVALID' in msg or 'API key not valid' in msg:
        print('INVALID    -> the key itself is wrong. Regenerate at aistudio.google.com/apikey')
    elif 'SERVICE_DISABLED' in msg or 'has not been used' in msg:
        print('DISABLED   -> enable Generative Language API on the project, then retry.')
    else:
        print('FAILED     ->', type(e).__name__, msg[:200])
    raise SystemExit(1)
"@
