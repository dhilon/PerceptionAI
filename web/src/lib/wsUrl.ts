export function wsDirectUrl(path = "/ws/stream", backendPort = 8001) {
    const host = window.location.hostname;                         // "localhost"
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${host}:${backendPort}${path}`;             // ws://localhost:8000/ws/stream
}