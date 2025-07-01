import React from 'react';

function Lobby({ players, onJoinGame, onStartGame, currentUserDiscordId }) {
  const hasJoined = players.some(p => p.discordId === currentUserDiscordId);

  return (
    <div className="bg-gray-700 p-8 rounded-lg shadow-xl w-full max-w-md text-center">
      <h2 className="text-2xl font-semibold mb-4 text-purple-300">Odotetaan pelaajia...</h2>
      <p className="mb-6 text-gray-300">Paina "Liity peliin" osallistuaksesi!</p>

      <div className="mb-6">
        <h3 className="text-xl font-medium mb-2 text-gray-200">Liittyneet pelaajat:</h3>
        {players.length > 0 ? (
          <ul className="list-disc list-inside text-left mx-auto max-w-xs text-gray-300">
            {players.map((player, index) => (
              <li key={player.discordId}>{player.name}</li>
            ))}
          </ul>
        ) : (
          <p className="text-gray-400">Ei vielä pelaajia.</p>
        )}
      </div>

      <div className="flex flex-col space-y-4">
        {!hasJoined ? (
          <button
            onClick={onJoinGame}
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg shadow-md transition duration-300 ease-in-out transform hover:scale-105"
          >
            Liity peliin!
          </button>
        ) : (
          <button
            onClick={onStartGame}
            className="bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-6 rounded-lg shadow-md transition duration-300 ease-in-out transform hover:scale-105"
          >
            Aloita peli!
          </button>
        )}
      </div>
    </div>
  );
}

export default Lobby;