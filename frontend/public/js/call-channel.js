import { validateUtterance } from './validation.js';

export function createCallChannel({ Client, brokerURL, callId, getAccessToken, myRole, onMessage, onReady, onDisconnect, onError }) {
    let closed = false;
    let ready = false;
    let subscription;
    const receivedIds = new Set();
    const client = new Client({
        brokerURL,
        reconnectDelay: 3000,
        connectionTimeout: 10000,
        beforeConnect: () => {
            client.connectHeaders = { Authorization: `Bearer ${getAccessToken()}` };
        },
        onConnect: () => {
            if (closed) return;
            ready = true;
            subscription?.unsubscribe();
            subscription = client.subscribe(`/topic/calls/${callId}`, frame => {
                let message;
                try {
                    message = JSON.parse(frame.body);
                } catch {
                    onError?.(new Error('소켓 메시지 형식을 확인해 주세요.'));
                    return;
                }
                if (closed || !message || typeof message !== 'object' || message.callId !== callId) return;
                if (message.type === 'translation') {
                    // 내 발화와 이미 받은 번역은 다시 표시하지 않습니다.
                    if (!message.utteranceId || message.senderRole === myRole || receivedIds.has(message.utteranceId)) return;
                    receivedIds.add(message.utteranceId);
                }
                onMessage(message);
            });
            onReady?.();
        },
        onWebSocketClose: () => { ready = false; if (!closed) onDisconnect?.(); },
        onStompError: () => { ready = false; if (!closed) onError?.(new Error('통화 채널에 연결하지 못했습니다.')); },
    });
    return {
        get connected() { return !closed && ready && client.connected; },
        start() { client.activate(); },
        send(text) {
            if (!validateUtterance(text)) throw new Error('발화는 1~2000자로 전달해 주세요.');
            if (closed || !ready || !client.connected) throw new Error('통화 채널이 연결되지 않았습니다.');
            client.publish({ destination: `/app/calls/${callId}/message`, body: JSON.stringify({ text }) });
        },
        stop() {
            closed = true;
            ready = false;
            try {
                if (client.connected) subscription?.unsubscribe();
            } catch {
                // 이미 끊어진 구독은 다시 해제하지 않습니다.
            } finally {
                subscription = null;
            }
            return client.deactivate();
        },
    };
}

let clientClassPromise;
export function loadStompClient() {
    if (globalThis.StompJs?.Client) return Promise.resolve(globalThis.StompJs.Client);
    if (!clientClassPromise) {
        clientClassPromise = new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = './vendor/stomp.umd.min.js';
            script.onload = () => globalThis.StompJs?.Client
                ? resolve(globalThis.StompJs.Client)
                : reject(new Error('STOMP 라이브러리를 확인해 주세요.'));
            script.onerror = () => {
                script.remove();
                reject(new Error('STOMP 라이브러리를 불러오지 못했습니다.'));
            };
            document.head.append(script);
        }).catch(error => {
            clientClassPromise = null;
            throw error;
        });
    }
    return clientClassPromise;
}
