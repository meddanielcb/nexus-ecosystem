"""
Fonte unica de verdade para entrega de acesso Nexus PlayTV / MasterX.

Todos os canais de entrega (bot Telegram, PDF VIP, cartao VIP, pagina web)
DEVEM importar daqui. Nunca duplicar literalmente esses dados em outro arquivo.

Dados oficiais do fornecedor MasterX (painel painelmaster.app):
  - Codigo de Aplicativos Parceiros: 00042
  - DNS homologados: atmt.space (principal) e atmt.store (alternativo)
  - APK direto MasterX: codigo Downloader 3054398
  - Windows: IPTV Smarters (instalador oficial do painel)
  - iPhone: VU Player Pro
"""

# ---------------------------------------------------------------------------
# Infra oficial
# ---------------------------------------------------------------------------
PAINEL_URL = "http://painelmaster.app"
PORTAL_URL = "http://painelmaster.app/portal"

SERVER_DNS_PRIMARY = "http://atmt.space"
SERVER_DNS_ALT = "http://atmt.store"
SERVER_DNS_ALL = (SERVER_DNS_PRIMARY, SERVER_DNS_ALT)

# Codigo Parceiro: campo POR APLICATIVO, cadastrado pelo revendedor em
# painelmaster.app/partner-apps (name, slug, api_type, api_base, partner_code,
# requires_mac, requires_key, requires_credentials).
# NAO existe codigo universal. "00042" e o codigo do app MASTERX (oficial Nexus)
# e tambem o valor de exemplo do formulario do painel.
PARTNER_APPS_CODE = "00042"          # codigo do app MASTERX (oficial)
PARTNER_APPS_CODE_IS_UNIVERSAL = False

PARTNER_CODE_HINT = (
    "Se o aplicativo pedir o *Código Parceiro*, use o código que aparece "
    "na própria tela dele ou peça ao nosso suporte."
)

# ---------------------------------------------------------------------------
# Aplicativos parceiros oficiais (aparecem dentro do app MasterX apos o codigo)
# ---------------------------------------------------------------------------
PARTNER_APPS = [
    "Magic PLAY",
    "Power Play",
    "ASSIST PLUS",
    "Lazer Play",
    "Super Play",
    "EPIC PLAY",
    "Play Sim",
    "Vizzion Play",
    "Box Player",
    "Blessed Play",
    "Fun Play",
]

# Aplicativos disponiveis na Google Play Store
PLAYSTORE_APPS = ["MASTERX", "XCIPTV", "Vizzion Play"]

# ---------------------------------------------------------------------------
# Instaladores diretos oficiais
# ---------------------------------------------------------------------------
MASTERX_DOWNLOADER_CODE = "3054398"
MASTERX_APK_URL = "http://aftv.news/3054398"
WINDOWS_SMARTERS_URL = "http://painelmaster.app/uploads/smarters-pc.exe"
IPHONE_APP = "VU Player Pro"

# ---------------------------------------------------------------------------
# Aplicativos com ativacao automatica por foto (nossos injetores)
# ---------------------------------------------------------------------------
AUTO_ACTIVATE_APPS = {
    "funplays": "FunPlays (funplays.app)",
    "siptv": "Smart IPTV (siptv.app / iptv.app)",
    "ibo": "IBO Player (iboplayer.com)",
    "smartone": "SmartOne IPTV (smartone-iptv.com)",
}


def apps_bullet_list() -> str:
    """Lista dos apps parceiros formatada para mensagens do Telegram."""
    return "\n".join(f"• {a}" for a in PARTNER_APPS)


def apps_inline() -> str:
    """Lista dos apps parceiros em uma unica linha (para cards e tabelas)."""
    return " | ".join(PARTNER_APPS)


def dns_bullet_list() -> str:
    return (f"• `{SERVER_DNS_PRIMARY}` (principal)\n"
            f"• `{SERVER_DNS_ALT}` (alternativo)")