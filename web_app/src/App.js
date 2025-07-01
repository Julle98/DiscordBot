import React, { useEffect, useState, useRef } from 'react';
import { DiscordSDK } from '@discord/embedded-app-sdk';
import io from 'socket.io-client';
import Lobby from './components/Lobby';
import Question from './components/Question';
import Results from './components/Results';

const BACKEND_URL = process.env.NODE_ENV === 'production' 
    ? 'https://your-hosted-backend-url.com' // VAIHDA TÄMÄ!
    : 'http://localhost:3001'; // Kehityksessä

const discordSdk = new DiscordSDK(import.meta.env.VITE_DISCORD_CLIENT_ID); // HAE TÄMÄ .env-tiedostosta

function App() {
  const [discordAuth, setDiscordAuth] = useState(null);
  const [gameState, setGameState] = useState({
    gameActive: false,
    players: {},
    currentQuestion: null,
    questionNumber: 0,
    totalQuestions: 0,
    correctAnswer: null,
    roundEnded: false,
    results: null,
  });
  const socketRef = useRef(null);

  useEffect(() => {
    async function setupDiscordSdk() {
      await discordSdk.ready();
      console.log("Discord SDK valmis!");

      const { access_token } = await discordSdk.commands.authenticate({
        withGuilds: false,
        withDiscordSync: false,
        withActivitiesRead: true,
        withConnections: false,
        withEmail: false,
      });

      const user = await fetch('https://discord.com/api/users/@me', {
        headers: {
          Authorization: `Bearer ${access_token}`,
        },
      }).then(res => res.json());

      setDiscordAuth({ user, access_token });

      const socket = io(BACKEND_URL);
      socketRef.current = socket;

      socket.on('connect', () => {
        console.log('Yhdistetty backend-palvelimeen!');
      });

      socket.on('game_state', (state) => {
        console.log('Initial game state:', state);
        setGameState(prev => ({
          ...prev,
          gameActive: state.gameActive,
          players: state.players,
          currentQuestion: state.currentQuestion,
          questionNumber: state.currentQuestion ? state.currentQuestion.questionNumber : 0,
          totalQuestions: state.currentQuestion ? state.currentQuestion.totalQuestions : 0,
          results: state.gameActive ? null : state.players, 
        }));
      });

      socket.on('game_started', () => {
        console.log('Peli aloitettu!');
        setGameState(prev => ({
          ...prev,
          gameActive: true,
          players: {},
          currentQuestion: null,
          questionNumber: 0,
          totalQuestions: 0,
          correctAnswer: null,
          roundEnded: false,
          results: null,
        }));
      });

      socket.on('player_joined', (updatedPlayers) => {
        console.log('Pelaaja liittyi:', updatedPlayers);
        setGameState(prev => ({ ...prev, players: updatedPlayers }));
      });

      socket.on('new_question', (data) => {
        console.log('Uusi kysymys:', data);
        setGameState(prev => ({
          ...prev,
          currentQuestion: data,
          questionNumber: data.questionNumber,
          totalQuestions: data.totalQuestions,
          correctAnswer: null, 
          roundEnded: false,
        }));
      });

      socket.on('answer_correct', (data) => {
        console.log('Oikea vastaus:', data);
        setGameState(prev => {
          const newPlayers = { ...prev.players };
          if (newPlayers[data.discordId]) {
            newPlayers[data.discordId].score = data.score;
          }
          return {
            ...prev,
            players: newPlayers,
          };
        });
      });

      socket.on('answer_wrong', (data) => {
        console.log('Väärä vastaus:', data);
      });

      socket.on('question_timeout', (data) => {
        console.log('Kysymys aikakatkaistu. Oikea vastaus:', data.correctAnswer);
        setGameState(prev => ({
          ...prev,
          correctAnswer: data.correctAnswer,
          roundEnded: true,
        }));
      });

      socket.on('game_ended', (finalResults) => {
        console.log('Peli päättynyt! Tulokset:', finalResults);
        setGameState(prev => ({
          ...prev,
          gameActive: false,
          currentQuestion: null,
          results: finalResults,
        }));
      });

      socket.on('error', (message) => {
        console.error('Backend error:', message);
        alert(`Virhe: ${message}`); 
      });

      return () => {
        socket.disconnect();
      };
    }

    setupDiscordSdk();
  }, []);

  const handleJoinGame = () => {
    if (socketRef.current && discordAuth) {
      socketRef.current.emit('join_game', {
        discordId: discordAuth.user.id,
        name: discordAuth.user.username,
      });
    }
  };

  const handleStartGame = () => {
    if (socketRef.current) {
      socketRef.current.emit('start_game');
    }
  };

  const handleSubmitAnswer = (answer) => {
    if (socketRef.current && discordAuth) {
      socketRef.current.emit('submit_answer', {
        discordId: discordAuth.user.id,
        answer: answer,
      });
    }
  };

  if (!discordAuth) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-800 text-white">
        Ladataan Discord SDK:ta...
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen w-full p-4 bg-gray-800 text-white font-inter rounded-lg shadow-lg">
      <h1 className="text-4xl font-bold mb-8 text-purple-400">Discord Tietovisa</h1>

      {!gameState.gameActive && !gameState.results && (
        <Lobby
          players={Object.values(gameState.players)}
          onJoinGame={handleJoinGame}
          onStartGame={handleStartGame}
          currentUserDiscordId={discordAuth.user.id}
        />
      )}

      {gameState.gameActive && gameState.currentQuestion && (
        <Question
          questionData={gameState.currentQuestion}
          questionNumber={gameState.questionNumber}
          totalQuestions={gameState.totalQuestions}
          onSubmitAnswer={handleSubmitAnswer}
          correctAnswer={gameState.correctAnswer}
          roundEnded={gameState.roundEnded}
        />
      )}

      {!gameState.gameActive && gameState.results && (
        <Results players={gameState.results} />
      )}
    </div>
  );
}

export default App;