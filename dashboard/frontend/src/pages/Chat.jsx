import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [ws, setWs] = useState(null)
  const [connected, setConnected] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    // Connect to WebSocket with optional token
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const token = localStorage.getItem('api_token') || ''
    const wsUrl = token
      ? `${protocol}//${window.location.hostname}:8000/ws?token=${encodeURIComponent(token)}`
      : `${protocol}//${window.location.hostname}:8000/ws`
    const socket = new WebSocket(wsUrl)

    socket.onopen = () => {
      console.log('WebSocket connected')
      setConnected(true)
    }

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data)

      // Handle different WebSocket frame types
      if (data.type === 'res') {
        // Response to our request
        if (data.ok && data.payload) {
          setMessages((prev) => [...prev, {
            id: Date.now(),
            role: 'assistant',
            content: `Work order created: ${data.payload.work_order_id}\nDifficulty: ${data.payload.difficulty}\nOwner: ${data.payload.owner}`,
            timestamp: new Date().toISOString(),
          }])
        } else if (!data.ok) {
          setMessages((prev) => [...prev, {
            id: Date.now(),
            role: 'error',
            content: `Error: ${data.error || 'Unknown error'}`,
            timestamp: new Date().toISOString(),
          }])
        }
      } else if (data.type === 'event') {
        // Server event (e.g., connected, chat.ack)
        console.log('WebSocket event:', data.event, data.payload)
        if (data.event === 'chat.ack') {
          // Optionally update UI to show acknowledgment
          console.log('Message acknowledged:', data.payload)
        }
      }
    }

    socket.onerror = (error) => {
      console.error('WebSocket error:', error)
      setConnected(false)
    }

    socket.onclose = () => {
      console.log('WebSocket disconnected')
      setConnected(false)
    }

    setWs(socket)

    return () => {
      socket.close()
    }
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim()) return

    const messageContent = input
    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: messageContent,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')

    if (ws && ws.readyState === WebSocket.OPEN) {
      // Send via WebSocket with correct format: {type: "req", id: "...", method: "chat.send", params: {content: "..."}}
      ws.send(JSON.stringify({
        type: 'req',
        id: `msg_${Date.now()}`,
        method: 'chat.send',
        params: {
          content: messageContent,
        },
      }))
    } else {
      // Fallback to HTTP
      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: input }),
        })
        const data = await res.json()

        if (data.ok) {
          setMessages((prev) => [...prev, {
            id: Date.now() + 1,
            role: 'assistant',
            content: `Work order created: ${data.work_order_id}\nDifficulty: ${data.difficulty}\nOwner: ${data.owner}`,
            timestamp: new Date().toISOString(),
          }])
        } else {
          setMessages((prev) => [...prev, {
            id: Date.now() + 1,
            role: 'error',
            content: `Error: ${data.error}`,
            timestamp: new Date().toISOString(),
          }])
        }
      } catch (error) {
        console.error('Failed to send message:', error)
        setMessages((prev) => [...prev, {
          id: Date.now() + 1,
          role: 'error',
          content: `Error: ${error.message}`,
          timestamp: new Date().toISOString(),
        }])
      }
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex h-screen flex-col bg-bg-primary">
      {/* Header */}
      <div className="border-b border-border-primary bg-bg-secondary px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-text-primary">NEXUS Chat</h1>
            <p className="text-sm text-text-secondary">
              Talk to your AI team
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm text-text-secondary">
              {connected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <h2 className="text-xl font-semibold text-text-secondary">
                Start a conversation
              </h2>
              <p className="mt-2 text-sm text-text-tertiary">
                Send a message to get started with NEXUS
              </p>
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : msg.role === 'error'
                      ? 'bg-red-600 text-white'
                      : 'bg-bg-secondary text-text-primary'
                  }`}
                >
                  <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                  <div className="mt-1 text-xs opacity-70">
                    {new Date(msg.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              </motion.div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-border-primary bg-bg-secondary px-6 py-4">
        <div className="mx-auto max-w-3xl">
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
              className="flex-1 rounded-lg border border-border-primary bg-bg-primary px-4 py-3 text-text-primary placeholder-text-tertiary focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              rows={3}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim()}
              className="rounded-lg bg-blue-600 px-6 py-3 font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
