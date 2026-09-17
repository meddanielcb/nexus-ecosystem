/* Public PWA shell only. Never cache account, payment, playlist, API or HTML responses. */
const CACHE='nexus-public-v1';
const OFFLINE='/app-assets/offline.html';
const PUBLIC=[OFFLINE,'/app-assets/icon-192.png','/app-assets/icon-512.png'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(PUBLIC))));
self.addEventListener('activate',event=>event.waitUntil(Promise.all([caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('nexus-public-')&&k!==CACHE).map(k=>caches.delete(k)))),self.clients.claim()])));
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url);
 if(request.method!=='GET'||url.origin!==self.location.origin)return;
 if(request.mode==='navigate'&&(url.pathname==='/app'||url.pathname.startsWith('/app/'))){event.respondWith(fetch(request).catch(()=>caches.match(OFFLINE)));return;}
 if(!PUBLIC.includes(url.pathname))return;
 event.respondWith(caches.match(request).then(cached=>cached||fetch(request)));
});
// Ready for a future authenticated Web Push sender. No subscription or sender is configured in this revision.
self.addEventListener('push',event=>{
 let payload;try{payload=event.data?.json()}catch{return}
 if(!payload||typeof payload.title!=='string'||typeof payload.body!=='string')return;
 event.waitUntil(self.registration.showNotification(payload.title.slice(0,100),{body:payload.body.slice(0,240),icon:'/app-assets/icon-192.png',badge:'/app-assets/icon-192.png',tag:typeof payload.id==='string'?payload.id.slice(0,100):'nexus',data:{url:'/app'}}));
});
self.addEventListener('notificationclick',event=>{
 event.notification.close();event.waitUntil(self.clients.matchAll({type:'window',includeUncontrolled:true}).then(windows=>{const client=windows.find(w=>new URL(w.url).origin===self.location.origin&&new URL(w.url).pathname==='/app');return client?client.focus():self.clients.openWindow('/app')}));
});
