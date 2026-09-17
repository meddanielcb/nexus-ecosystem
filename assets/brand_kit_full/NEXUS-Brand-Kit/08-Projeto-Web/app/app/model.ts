export type Sport='Futebol'|'Basquete'|'Lutas';
export type Game={id:string,home:string,away:string,time:string,competition:string,sport:Sport,day:number,channel:string|null,tags:string[]};
export const demoGames:Game[]=[
{id:'fla-pal',home:'Flamengo',away:'Palmeiras',time:'19:00',competition:'Brasileirão • Série A',sport:'Futebol',day:0,channel:'premiere',tags:['Flamengo','Palmeiras']},
{id:'real-barca',home:'Real Madrid',away:'Barcelona',time:'21:00',competition:'LaLiga',sport:'Futebol',day:0,channel:'espn',tags:['Real Madrid','Barcelona']},
{id:'lal-gsw',home:'Lakers',away:'Warriors',time:'22:30',competition:'NBA',sport:'Basquete',day:0,channel:'sportv',tags:['Lakers','Warriors']},
{id:'ufc',home:'UFC',away:'Card principal',time:'23:00',competition:'MMA • Octógono',sport:'Lutas',day:0,channel:null,tags:['UFC','Poatan']},
{id:'pal-real',home:'Palmeiras',away:'Flamengo',time:'20:30',competition:'Copa • Futebol',sport:'Futebol',day:1,channel:'premiere',tags:['Palmeiras','Flamengo']},
];
export const channels=[
{id:'premiere',name:'Premiere',file:'premiere.svg',category:'Esportes',number:'101',now:'Pré-jogo: futebol brasileiro',next:'19:00 · Flamengo × Palmeiras',start:18*60,end:19*60},
{id:'sportv',name:'SporTV',file:'sportv.svg',category:'Esportes',number:'102',now:'Redação esportiva',next:'19:30 · Giro do esporte',start:18*60+30,end:19*60+30},
{id:'espn',name:'ESPN',file:'espn.png',category:'Esportes',number:'103',now:'Central do esporte',next:'20:00 · Aquecimento LaLiga',start:18*60,end:20*60},
{id:'hbo',name:'HBO',file:'hbo.svg',category:'Filmes e séries',number:'201',now:'Sessão de cinema',next:'20:10 · Próxima sessão',start:18*60+10,end:20*60+10},
];
export const favoriteOptions=['Flamengo','Palmeiras','Real Madrid','Barcelona','Lakers','Warriors','UFC','Poatan'];
export type Preferences={favorites:string[],alerts:{gameDay:boolean,kickoff:boolean,renewal:boolean}};
export const defaults:Preferences={favorites:[],alerts:{gameDay:true,kickoff:true,renewal:true}};
export function parsePreferences(value:string|null):Preferences{try{const x=JSON.parse(value||'null');if(!x)return defaults;return{favorites:Array.isArray(x.favorites)?x.favorites.filter((f:unknown)=>typeof f==='string'&&favoriteOptions.includes(f)):[],alerts:{gameDay:typeof x.alerts?.gameDay==='boolean'?x.alerts.gameDay:true,kickoff:typeof x.alerts?.kickoff==='boolean'?x.alerts.kickoff:true,renewal:typeof x.alerts?.renewal==='boolean'?x.alerts.renewal:true}}}catch{return defaults}}
export const normalize=(s:string)=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
export function filterGames(games:Game[],query:string,sport:string,day:number,favorites:string[],onlyFavorites:boolean){return games.filter(g=>g.day===day&&(sport==='Todos'||g.sport===sport)&&(!onlyFavorites||g.tags.some(t=>favorites.includes(t)))&&normalize(g.home+' '+g.away+' '+g.competition).includes(normalize(query)))}
export function daysRemaining(expiresAt:string,now:Date){const end=Date.parse(expiresAt);return Number.isFinite(end)?Math.max(0,Math.ceil((end-now.getTime())/86400000)):0}
export function progress(start:number,end:number,now:number){return end>start?Math.max(0,Math.min(100,(now-start)/(end-start)*100)):0}
