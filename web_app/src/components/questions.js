// web_app/src/components/Question.js
import React from 'react';

function Question({ questionData, questionNumber, totalQuestions, onSubmitAnswer, correctAnswer, roundEnded }) {
  const handleAnswerClick = (answer) => {
    if (!roundEnded) { // Estä vastaaminen, jos kierros on päättynyt
      onSubmitAnswer(answer);
    }
  };

  return (
    <div className="bg-gray-700 p-8 rounded-lg shadow-xl w-full max-w-lg text-center">
      <h2 className="text-xl font-semibold mb-4 text-purple-300">
        Kysymys {questionNumber}/{totalQuestions}
      </h2>
      <p className="text-3xl font-bold mb-8 text-white">{questionData.question}</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {questionData.options.map((option, index) => (
          <button
            key={index}
            onClick={() => handleAnswerClick(option)}
            className={`
              py-3 px-6 rounded-lg shadow-md transition duration-300 ease-in-out transform hover:scale-105
              ${roundEnded 
                ? (option === correctAnswer ? 'bg-green-600' : 'bg-red-600 opacity-70 cursor-not-allowed')
                : 'bg-blue-600 hover:bg-blue-700'
              }
              text-white font-bold
            `}
            disabled={roundEnded} // Disabloi painikkeet, kun kierros on päättynyt
          >
            {option}
          </button>
        ))}
      </div>

      {roundEnded && correctAnswer && (
        <p className="text-xl font-semibold text-green-400 mt-4">
          Oikea vastaus oli: **{correctAnswer}**
        </p>
      )}
    </div>
  );
}

export default Question;