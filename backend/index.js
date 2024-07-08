const fs = require('fs');
const path = require('path');

const express = require('express');
const morgan = require('morgan');
const cors = require('cors');

const app = express();
app.use(morgan('tiny'))

// enable CORS and serve layers in development
if (process.env.NODE_ENV === 'development') {
    app.use(cors());
    app.use('/layers', express.static(path.join(__dirname, 'layers')));
}

app.get('/api/forecast_cycle', (req, res) => {
    try {
        const currentPath = path.join(__dirname, 'layers', 'current');

        if (fs.existsSync(currentPath) && fs.lstatSync(currentPath).isSymbolicLink()) {
            const currentCycle = fs.readlinkSync(currentPath);
            const startDatetime = new Date(`${currentCycle}:00:00.000`);
            const numForecasts = fs.readdirSync(currentPath).length;

            return res.json({
                startDatetime: startDatetime.toISOString(),
                numForecasts: numForecasts
            });
        }
        throw new Error("Path does not exist or is not a symbolic link");
    } catch (error) {
        res.status(500).json({ detail: "Internal Server Error" });
    }
});

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});
