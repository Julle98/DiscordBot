import React from 'react';

function Results({ players }) {
  const sortedPlayers = Object.values(players).sort((a, b) => b.score - a.score);

  return (
    <div className="bg-gray-700 p-8 rounded-lg shadow-xl w-full max-w-md text-center">
      <h2 className="text-3xl font-bold mb-6 text-yellow-400">🏆 Pelin lopputulokset 🏆</h2>
      
      {sortedPlayers.length > 0 ? (
        <ul className="list-none p-0 text-left mx-auto max-w-xs">
          {sortedPlayers.map((player, index) => (
            <li 
              key={player.discordId} 
              className={`text-xl py-2 border-b border-gray-600 last:border-b-0 
                ${index === 0 ? 'text-yellow-300 font-extrabold' : 'text-gray-200'}`}
            >
              {index + 1}. {player.name}: <span className="font-bold">{player.score}</span> pistettä
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-gray-400">Ei tuloksia näytettävänä.</p>
      )}

      <p className="mt-8 text-gray-300">Kiitos pelaamisesta!</p>
    </div>
  );
}

export default Results;