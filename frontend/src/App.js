import React, { useState, useEffect, useRef } from "react";
import "./App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://');

function App() {
  const [robotState, setRobotState] = useState({
    status: "idle",
    progress: 0,
    is_cleaning: false,
    obstacle_detected: false,
    start_time: null,
    current_mode: null,
    pause_reason: null
  });
  
  const [notifications, setNotifications] = useState([]);
  const [cleaningLogs, setCleaningLogs] = useState([]);
  const [selectedMode, setSelectedMode] = useState("full_clean");
  const [loading, setLoading] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  
  const wsRef = useRef(null);

  // WebSocket connection
  useEffect(() => {
    connectWebSocket();
    fetchCleaningLogs();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const connectWebSocket = () => {
    try {
      wsRef.current = new WebSocket(`${WS_URL}/api/ws`);
      
      wsRef.current.onopen = () => {
        console.log("WebSocket connected");
      };
      
      wsRef.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === "status_update") {
          setRobotState(data.robot_state);
        } else if (data.type === "alert" || data.type === "info" || data.type === "cleaning_complete") {
          addNotification(data.message, data.type);
          if (data.robot_state) {
            setRobotState(data.robot_state);
          }
          if (data.type === "cleaning_complete") {
            fetchCleaningLogs(); // Refresh logs when cleaning completes
          }
        }
      };
      
      wsRef.current.onclose = () => {
        console.log("WebSocket disconnected, attempting to reconnect...");
        setTimeout(connectWebSocket, 3000);
      };
      
    } catch (error) {
      console.error("WebSocket connection error:", error);
    }
  };

  const addNotification = (message, type) => {
    const notification = {
      id: Date.now(),
      message,
      type,
      timestamp: new Date()
    };
    
    setNotifications(prev => [notification, ...prev].slice(0, 5)); // Keep only 5 recent notifications
    
    // Auto-remove notification after 5 seconds
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== notification.id));
    }, 5000);
  };

  const sendRobotCommand = async (command, mode = selectedMode) => {
    setLoading(true);
    try {
      const response = await axios.post(`${API}/robot/command`, {
        command,
        mode
      });
      
      if (response.data.success) {
        addNotification(response.data.message, "info");
        if (response.data.robot_state) {
          setRobotState(response.data.robot_state);
        }
      } else {
        addNotification(response.data.message, "alert");
      }
    } catch (error) {
      addNotification("Failed to communicate with robot", "alert");
      console.error("Command error:", error);
    }
    setLoading(false);
  };

  const fetchCleaningLogs = async () => {
    try {
      const response = await axios.get(`${API}/cleaning-logs`);
      setCleaningLogs(response.data);
    } catch (error) {
      console.error("Failed to fetch cleaning logs:", error);
    }
  };

  const getStatusDisplay = () => {
    const statusMap = {
      idle: { text: "🏠 Ready", color: "text-gray-600", bg: "bg-gray-100" },
      mopping: { text: "🧽 Mopping Floor", color: "text-blue-600", bg: "bg-blue-100" },
      spraying: { text: "💧 Spraying Sanitizer", color: "text-green-600", bg: "bg-green-100" },
      uv_disinfecting: { text: "🔬 UV-C Disinfecting", color: "text-purple-600", bg: "bg-purple-100" },
      paused: { text: "⏸️ Paused", color: "text-yellow-600", bg: "bg-yellow-100" }
    };
    
    return statusMap[robotState.status] || statusMap.idle;
  };

  const getModeDisplay = (mode) => {
    const modeMap = {
      full_clean: "🔄 Full Clean",
      mop_only: "🧽 Mop Only", 
      spray_only: "💧 Spray Only",
      uv_only: "🔬 UV-C Only"
    };
    return modeMap[mode] || mode;
  };

  const formatDuration = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const statusDisplay = getStatusDisplay();

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-md mx-auto">
        
        {/* Header */}
        <div className="text-center mb-6">
          <div className="w-20 h-20 mx-auto mb-4 rounded-full overflow-hidden shadow-lg">
            <img 
              src="https://images.unsplash.com/photo-1558317374-067fb5f30001?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2Mzl8MHwxfHNlYXJjaHwxfHxjbGVhbmluZyUyMHJvYm90fGVufDB8fHx8MTc1MzcwNDY3NHww&ixlib=rb-4.1.0&q=85" 
              alt="Cleaning Robot"
              className="w-full h-full object-cover"
            />
          </div>
          <h1 className="text-2xl font-bold text-gray-800 mb-1">Robot Control</h1>
          <p className="text-gray-600 text-sm">Autonomous Floor Sanitizer</p>
        </div>

        {/* Status Card */}
        <div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
          <div className={`${statusDisplay.bg} ${statusDisplay.color} rounded-xl p-4 text-center mb-4`}>
            <div className="text-2xl font-bold mb-1">{statusDisplay.text}</div>
            {robotState.obstacle_detected && (
              <div className="text-red-600 text-sm font-medium">⚠️ Obstacle Detected</div>
            )}
          </div>
          
          {/* Progress Bar */}
          {robotState.is_cleaning && (
            <div className="mb-4">
              <div className="flex justify-between text-sm text-gray-600 mb-2">
                <span>Progress</span>
                <span>{robotState.progress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div 
                  className="bg-blue-500 h-3 rounded-full transition-all duration-500"
                  style={{ width: `${robotState.progress}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Mode Selection */}
        {!robotState.is_cleaning && (
          <div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
            <h3 className="text-lg font-semibold mb-4">Select Cleaning Mode</h3>
            <div className="grid grid-cols-2 gap-3">
              {[
                { key: "full_clean", label: "🔄 Full Clean", desc: "Complete cycle" },
                { key: "mop_only", label: "🧽 Mop Only", desc: "Floor mopping" },
                { key: "spray_only", label: "💧 Spray Only", desc: "Sanitizer spray" },
                { key: "uv_only", label: "🔬 UV-C Only", desc: "UV disinfection" }
              ].map(mode => (
                <button
                  key={mode.key}
                  onClick={() => setSelectedMode(mode.key)}
                  className={`p-3 rounded-xl border-2 text-left transition-all ${
                    selectedMode === mode.key 
                      ? 'border-blue-500 bg-blue-50 text-blue-700' 
                      : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                  }`}
                >
                  <div className="font-medium text-sm">{mode.label}</div>
                  <div className="text-xs opacity-75">{mode.desc}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Control Buttons */}
        <div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
          <div className="space-y-3">
            {!robotState.is_cleaning ? (
              <button
                onClick={() => sendRobotCommand("start")}
                disabled={loading}
                className="w-full bg-green-500 hover:bg-green-600 text-white font-bold py-4 px-6 rounded-xl text-lg shadow-lg transition-all transform active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "🔄 Starting..." : "🚀 Start Cleaning"}
              </button>
            ) : (
              <div className="space-y-3">
                {robotState.status === "paused" ? (
                  <button
                    onClick={() => sendRobotCommand("resume")}
                    disabled={loading}
                    className="w-full bg-blue-500 hover:bg-blue-600 text-white font-bold py-4 px-6 rounded-xl text-lg shadow-lg transition-all transform active:scale-95 disabled:opacity-50"
                  >
                    {loading ? "🔄 Resuming..." : "▶️ Resume Cleaning"}
                  </button>
                ) : (
                  <button
                    onClick={() => sendRobotCommand("pause")}
                    disabled={loading}
                    className="w-full bg-yellow-500 hover:bg-yellow-600 text-white font-bold py-4 px-6 rounded-xl text-lg shadow-lg transition-all transform active:scale-95 disabled:opacity-50"
                  >
                    {loading ? "🔄 Pausing..." : "⏸️ Pause Cleaning"}
                  </button>
                )}
                
                <button
                  onClick={() => sendRobotCommand("stop")}
                  disabled={loading}
                  className="w-full bg-red-500 hover:bg-red-600 text-white font-bold py-4 px-6 rounded-xl text-lg shadow-lg transition-all transform active:scale-95 disabled:opacity-50"
                >
                  {loading ? "🔄 Stopping..." : "🛑 Stop Cleaning"}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Notifications */}
        {notifications.length > 0 && (
          <div className="mb-6 space-y-2">
            {notifications.map(notification => (
              <div
                key={notification.id}
                className={`p-3 rounded-xl shadow-lg ${
                  notification.type === "alert" 
                    ? "bg-red-100 text-red-700 border-l-4 border-red-500" 
                    : notification.type === "cleaning_complete"
                    ? "bg-green-100 text-green-700 border-l-4 border-green-500"
                    : "bg-blue-100 text-blue-700 border-l-4 border-blue-500"
                }`}
              >
                <div className="font-medium text-sm">{notification.message}</div>
                <div className="text-xs opacity-75">
                  {notification.timestamp.toLocaleTimeString()}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Cleaning Logs */}
        <div className="bg-white rounded-2xl shadow-lg p-6">
          <button
            onClick={() => setShowLogs(!showLogs)}
            className="w-full flex justify-between items-center mb-4"
          >
            <h3 className="text-lg font-semibold">📋 Cleaning History</h3>
            <span className="text-gray-400">
              {showLogs ? "▼" : "▶"}
            </span>
          </button>
          
          {showLogs && (
            <div className="space-y-3">
              {cleaningLogs.length === 0 ? (
                <p className="text-gray-500 text-center py-4">No cleaning sessions yet</p>
              ) : (
                cleaningLogs.slice(0, 10).map(log => (
                  <div key={log.id} className="border border-gray-200 rounded-xl p-4">
                    <div className="flex justify-between items-start mb-2">
                      <div className="font-medium text-sm">
                        {getModeDisplay(log.mode)}
                      </div>
                      <div className={`px-2 py-1 rounded-full text-xs font-medium ${
                        log.status === "completed" 
                          ? "bg-green-100 text-green-600" 
                          : "bg-yellow-100 text-yellow-600"
                      }`}>
                        {log.status}
                      </div>
                    </div>
                    <div className="text-xs text-gray-600">
                      <div>Started: {new Date(log.start_time).toLocaleString()}</div>
                      {log.duration && (
                        <div>Duration: {formatDuration(log.duration)}</div>
                      )}
                      {log.progress !== undefined && (
                        <div>Progress: {log.progress}%</div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;