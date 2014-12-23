// setup.js
exports.config = {
	capabilities: {
		browserName: 'chrome',
		maxInstances: 1 
	},
	seleniumAddress: 'http://localhost:4444/wd/hub', 
	specs: ['farmer_splash.js', 'farmer-signup.js'],
	allScriptsTimeout: 100000,

}