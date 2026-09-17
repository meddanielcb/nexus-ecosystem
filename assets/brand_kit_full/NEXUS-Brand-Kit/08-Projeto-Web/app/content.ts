export const contact = 'https://t.me/Nexus_playtvbot';
export const plans = [
 {id:'monthly',name:'Mensal',days:30,months:1,prices:[31.90,42.80,53.70],tag:'Liberdade para começar'},
 {id:'quarterly',name:'Trimestral',days:90,months:3,prices:[79.90,109.90,139.90],tag:'Mais tempo para descobrir'},
 {id:'semiannual',name:'Semestral',days:180,months:6,prices:[149.90,209.90,259.90],tag:'Entretenimento no seu ritmo'},
 {id:'annual',name:'Anual VIP',days:365,months:12,prices:[249.90,349.90,439.90],tag:'Melhor valor por mês'},
];
export const money=(v:number)=>v.toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
export const categories=['Futebol','Basquete','Ação','Suspense','Automobilismo','Para a família','Música'];
export const devices=[
 {name:'Smart TV',models:'Samsung · LG · TCL · Roku TV · Philips',body:'O modelo, o ano e o sistema da sua TV determinam qual aplicativo pode ser instalado. A ativação por foto depende do aplicativo compatível.'},
 {name:'Celular e tablet',models:'Android · iPhone · iPad',body:'Assista em um aplicativo compatível com a versão do seu sistema. Consulte a indicação de aplicativo e a disponibilidade da ativação para o seu aparelho.'},
 {name:'Computador',models:'Windows · Mac',body:'Consulte o player indicado para seu sistema. O Cartão VIP reúne as informações necessárias para configurar o acesso.'},
 {name:'Streaming',models:'Fire TV Stick · TV Box · Chromecast · Apple TV',body:'A instalação varia conforme modelo e sistema. Chromecast pode depender da transmissão a partir de outro aparelho. Confirme a opção para seu dispositivo.'},
];
export const faqs=[
 ['Tem o canal ou título que eu quero assistir?','Consulte o catálogo e a grade pelo Telegram antes de contratar. As marcas e imagens desta vitrine não significam que o plano inclui contas individuais de Netflix, Disney+, Prime Video ou outras plataformas.'],
 ['Como a NEXUS enfrenta travamentos e atraso?','O StreamCore™ Ultra-P2P é a rede anti-bloqueio de operadoras informada pela marca, com distribuição redundante. A Engine Go™ Anti-Delay trabalha a latência do futebol. A experiência também depende da fonte, conexão, aplicativo e aparelho.'],
 ['Como funciona a ativação por foto?','Abra o aplicativo compatível na TV e envie uma foto da tela pelo canal indicado após a compra. O Nexus Vision AI identifica os dados de configuração. Os 15 segundos são uma referência informada pela marca para aparelhos e aplicativos compatíveis, não um prazo universal.'],
 ['Minha TV é compatível?','A compatibilidade depende do modelo, ano, sistema e aplicativo disponível. Consulte seu aparelho no Telegram antes de escolher o plano. Nem todos os aparelhos permitem ativação por foto.'],
 ['Preciso instalar algum aplicativo?','Em geral, você precisa de um player compatível no aparelho. A equipe orienta qual usar após verificar o modelo e o sistema.'],
 ['O aplicativo tem custo separado?','Alguns players podem exigir uma licença própria, não incluída no valor do plano NEXUS. Confirme o aplicativo e eventual custo antes de contratar.'],
 ['Quantas telas posso usar?','Os planos de 30, 90, 180 e 365 dias permitem escolher 1, 2 ou 3 telas. O valor total muda conforme sua escolha. Consulte as condições específicas do Pass Avulso.'],
 ['Como recebo o Cartão VIP?','Após a confirmação do pagamento, a entrega prevista reúne login, senha, DNS e instruções no Cartão VIP, com opção de PDF. As credenciais também são previstas para WhatsApp e Telegram. O tempo de confirmação depende do meio de pagamento.'],
 ['Quais pagamentos são aceitos?','O fluxo prevê PIX por QR Code ou Copia e Cola via Pixget, e USDT ou BTC via BlockBee. Nesta versão de revisão, nenhum pagamento é gerado ou cobrado.'],
 ['Qual conexão é recomendada?','A necessidade varia com resolução, fonte, aparelho e quantidade de telas. Prefira uma conexão estável, por cabo quando possível, e confirme a recomendação para a qualidade desejada.'],
 ['Como funciona o atendimento?','Fale com a NEXUS no Telegram para consultar compatibilidade, instalação e condições comerciais. O processamento de entrega 24/7 não significa atendimento humano ininterrupto.'],
 ['Como solicito cancelamento ou reembolso?','Consulte pelo Telegram a política aplicável e o procedimento antes de contratar. As condições de renovação, cancelamento e reembolso devem fazer parte da confirmação da sua compra.'],
];
export const integrationContract={enabled:false,checkout:'/api/checkout',paymentStatus:'/api/orders/:id',webhook:'/api/webhooks/:provider',fulfillment:'/api/orders/:id/vip',providers:['pixget','blockbee'],rule:'Only a verified server webhook may mark payment confirmed. Never trust query strings or browser state.'};
