export const asset=(name:string)=>'/media/'+name;

export type Brand={name:string;file:string};

export const brands:Brand[]=[
  {name:'Premiere',file:'premiere.svg'},
  {name:'SporTV',file:'sportv.svg'},
  {name:'ESPN',file:'espn.png'},
  {name:'UFC',file:'ufc.svg'},
  {name:'Combate',file:'combate.svg'},
  {name:'Champions League',file:'champions.svg'},
  {name:'Fórmula 1',file:'f1.svg'},
  {name:'Netflix',file:'netflix.svg'},
  {name:'Disney+',file:'disney.svg'},
  {name:'HBO Max',file:'hbo.svg'},
  {name:'Prime Video',file:'prime.svg'},
  {name:'Paramount+',file:'paramount.svg'},
  {name:'Globo',file:'globo.svg'},
  {name:'SBT',file:'sbt.svg'},
];

export const platforms:Brand[]=[
  {name:'Netflix',file:'netflix.svg'},
  {name:'Disney+',file:'disney.svg'},
  {name:'HBO Max',file:'hbo.svg'},
  {name:'Prime Video',file:'prime.svg'},
  {name:'Paramount+',file:'paramount.svg'},
  {name:'Globo',file:'globo.svg'},
  {name:'SBT',file:'sbt.svg'},
];

export const sportLogos={
  football:['Premiere','SporTV','ESPN','Champions League'],
  fight:['UFC','Combate','ESPN'],
  basket:['ESPN','SporTV','Prime Video'],
  motor:['Fórmula 1','ESPN','SporTV'],
};

export const entertainment=[
 {title:'Stranger Things',category:'SÉRIES',image:'stranger-things.webp',brand:'netflix.svg',position:'70% 50%'},
 {title:'Futebol',category:'ESPORTES',image:'football.webp',brand:'premiere.svg',position:'50% 50%'},
 {title:'Duna',category:'CINEMA',image:'dune.webp',brand:'hbo.svg',position:'50% 40%'},
 {title:'UFC',category:'LUTAS',image:'ufc.webp',brand:'ufc.svg',position:'50% 22%'},
 {title:'The Mandalorian',category:'SÉRIES',image:'mandalorian.webp',brand:'disney.svg',position:'50% 35%'},
 {title:'The Last of Us',category:'SÉRIES',image:'last-of-us.webp',brand:'hbo.svg',position:'50% 35%'},
 {title:'Wandinha',category:'SÉRIES',image:'wednesday.webp',brand:'netflix.svg',position:'50% 35%'},
];
