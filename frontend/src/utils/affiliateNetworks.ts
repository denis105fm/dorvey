/**
 * Ссылки на партнёрские сети (сайт / регистрация вебмастера).
 * Ключ — название сети в нижнем регистре для сопоставления с ответом AI.
 */
const AFFILIATE_NETWORK_URLS: Record<string, string> = {
  admitad: "https://www.admitad.com/",
  actionpay: "https://actionpay.ru/",
  "m1-shop": "https://m1-shop.ru/",
  leadgid: "https://leadgid.ru/",
  richleads: "https://richleads.ru/",
  epn: "https://epn.bz/",
  advertur: "https://advertur.ru/",
  "cpa.rbc": "https://cpa.rbc.ru/",
  everad: "https://everad.com/",
  moneyplace: "https://moneyplace.ru/",
  dr.cash: "https://drcash.ru/",
  leads.su: "https://leads.su/",
  adcombo: "https://adcombo.com/",
  clickadu: "https://clickadu.com/",
  mgid: "https://www.mgid.com/",
  propeller: "https://propellerads.com/",
};

export function getAffiliateNetworkUrl(network: string): string | null {
  if (!network || typeof network !== "string") return null;
  const key = network.trim().toLowerCase().replace(/\s+/g, " ");
  return AFFILIATE_NETWORK_URLS[key] ?? null;
}
