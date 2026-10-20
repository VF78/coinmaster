// Pass an existing sharp module path; this script installs nothing.
const fs = require('fs');
const path = require('path');
const sharp = require(process.argv[2] || 'sharp');
(async()=>{for(const name of ['charts-equity-drawdown','charts-monthly-returns']) {
 await sharp(path.join(__dirname,name+'.svg')).png().toFile(path.join(__dirname,name+'.png'));
}})().catch(e=>{console.error(e);process.exit(1)});
