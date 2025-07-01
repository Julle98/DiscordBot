const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const path = require('path');
const fs = require('fs');
const cors = require('cors'); 

const app = express();
const server = http.createServer(app);
const io = new socketIo.Server(server, {
    cors: {
        origin: "*", 
        methods: ["GET", "POST"]
    }
});

const PORT = process.env.PORT || 3001; 

let gameActive = false;
let currentQuestionIndex = -1;
let players = {}; 
let questions = [];
let questionTimeout = null;
let answeredPlayersThisRound = new Set(); 

const loadQuestions = () => {
    try {
        const questionsPath = path.join(__dirname, '..', 'data', 'questions.json');
        const data = fs.readFileSync(questionsPath, 'utf8');
        questions = JSON.parse(data);
        console.log(`Kysymyksiä ladattu: ${questions.length}`);
    } catch (error) {
        console.error("Virhe kysymysten latauksessa:", error);
        questions = [];
    }
};

loadQuestions();

app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/questions', (req, res) => {
    res.json(questions);
});

io.on('connection', (socket) => {
    console.log('Uusi käyttäjä yhdistetty:', socket.id);

    socket.emit('game_state', {
        gameActive: gameActive,
        players: players,
        currentQuestion: currentQuestionIndex !== -1 ? questions[currentQuestionIndex] : null,
        answeredPlayersThisRound: Array.from(answeredPlayersThisRound)
    });

    socket.on('join_game', (playerData) => {
        if (!gameActive) {
            socket.emit('error', 'Peli ei ole käynnissä tai liittymisaika on ohi.');
            return;
        }
        if (!players[playerData.discordId]) {
            players[playerData.discordId] = { score: 0, name: playerData.name };
            console.log(`${playerData.name} liittyi peliin.`);
            io.emit('player_joined', players); 
        } else {
            socket.emit('error', 'Olet jo liittynyt peliin.');
        }
    });

    socket.on('start_game', () => {
        if (gameActive) {
            console.log("Peli on jo käynnissä.");
            return;
        }
        if (questions.length === 0) {
            io.emit('error', 'Kysymyksiä ei ole ladattu. Peliä ei voi aloittaa.');
            return;
        }
        gameActive = true;
        players = {}; 
        currentQuestionIndex = -1;
        answeredPlayersThisRound.clear();
        io.emit('game_started');
        console.log("Peli aloitettu.");
        setTimeout(sendNextQuestion, 5000); 
    });

    socket.on('submit_answer', (data) => {
        if (!gameActive || currentQuestionIndex === -1) {
            socket.emit('error', 'Peli ei ole käynnissä tai kysymystä ei ole esitetty.');
            return;
        }
        if (!players[data.discordId]) {
            socket.emit('error', 'Et ole liittynyt peliin.');
            return;
        }
        if (answeredPlayersThisRound.has(data.discordId)) {
            socket.emit('error', 'Olet jo vastannut tähän kysymykseen.');
            return;
        }

        const currentQuestion = questions[currentQuestionIndex];
        if (data.answer === currentQuestion.oikea) {
            players[data.discordId].score += 1;
            answeredPlayersThisRound.add(data.discordId);
            io.emit('answer_correct', {
                discordId: data.discordId,
                name: players[data.discordId].name,
                score: players[data.discordId].score,
                answer: data.answer
            });
            console.log(`${players[data.discordId].name} vastasi oikein.`);

        } else {
            
            answeredPlayersThisRound.add(data.discordId);
            io.emit('answer_wrong', {
                discordId: data.discordId,
                name: players[data.discordId].name,
                answer: data.answer
            });
            console.log(`${players[data.discordId].name} vastasi väärin.`);
        }
    });

    socket.on('disconnect', () => {
        console.log('Käyttäjä irrotettu:', socket.id);
    });
});

const sendNextQuestion = () => {
    if (!gameActive) return;

    currentQuestionIndex++;
    answeredPlayersThisRound.clear(); 
    
    if (currentQuestionIndex < questions.length) {
        const question = questions[currentQuestionIndex];
        const options = [...question.vastaukset]; 
        
        options.sort(() => Math.random() - 0.5); 
        
        io.emit('new_question', {
            question: question.kysymys,
            options: options,
            questionNumber: currentQuestionIndex + 1,
            totalQuestions: questions.length
        });
        console.log(`Lähetetty kysymys ${currentQuestionIndex + 1}: ${question.kysymys}`);

        questionTimeout = setTimeout(() => {
            io.emit('question_timeout', {
                correctAnswer: questions[currentQuestionIndex].oikea
            });
            console.log(`Kysymys ${currentQuestionIndex + 1} aikakatkaistu.`);
            setTimeout(sendNextQuestion, 3000); 
        }, 15000); 
    } else {
        endGame();
    }
};

const endGame = () => {
    gameActive = false;
    currentQuestionIndex = -1;
    answeredPlayersThisRound.clear();
    const sortedPlayers = Object.values(players).sort((a, b) => b.score - a.score);
    io.emit('game_ended', sortedPlayers);
    console.log("Peli päättynyt.");
};

server.listen(PORT, () => {
    console.log(`Backend-palvelin käynnissä portissa ${PORT}`);
    console.log(`Web-sovellus tarjoillaan osoitteesta http://localhost:${PORT}`);
});