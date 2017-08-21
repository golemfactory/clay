var https = require( 'https' );

var pullRequestID = process.argv[2]
var options = {
	hostname:'api.github.com',
	path: `/repos/golemfactory/golem/pulls/${ pullRequestID }/reviews`,
	headers: {
		'User-Agent':'build-bot'
	}
};

https.get( options , res => {
	var body = '';
	res.on( 'data', a => body += a );
	res.on( 'end', () => {
		try {
			var jsonBody = JSON.parse( body );
			var approvals = jsonBody.filter( a => a.state === 'APPROVED' );
			console.log( approvals.length ) 
		}
		catch( e )
		{
			console.log( body );
			console.error( e );
		}
	} ); 
} );
