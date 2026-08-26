TRANSLATIONS = {
    'en': {
        'portal_title': 'Central Examination Authority 2026',
        'home_heading': 'Combined Entrance Examination (CEE-2026)',
        'register_btn': 'New Candidate Registration',
        'login_btn': 'Candidate Login',
        'track_btn': 'Track Application Status',
        'helpdesk_btn': 'Helpdesk Support',
        'toggle_lang_btn': '🇮🇳 हिंदी',
    },
    'hi': {
        'portal_title': 'केंद्रीय परीक्षा प्राधिकरण २०२६',
        'home_heading': 'संयुक्त प्रवेश परीक्षा (सीईई-२०२६)',
        'register_btn': 'नया उम्मीदवार पंजीकरण',
        'login_btn': 'उम्मीदवार लॉगिन',
        'track_btn': 'आवेदन की स्थिति ट्रैक करें',
        'helpdesk_btn': 'हेल्पडेस्क सहायता',
        'toggle_lang_btn': '🇬🇧 English',
    }
}

def get_trans(request):
    lang = request.session.get('portal_lang', 'en')
    return TRANSLATIONS.get(lang, TRANSLATIONS['en'])