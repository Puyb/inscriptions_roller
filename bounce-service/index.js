'use strict';
const Promise = require('bluebird');
const Imap = require('imap');
Promise.promisifyAll(Imap.prototype);
const { BounceHandler } = require('bounce-handler');
const Knex = require('knex');
const inspect = require('util').inspect;

//const config = require('./config.json');
const config = {
    imap: {
        user: process.env.EMAIL_HOST_USER,
        password: process.env.EMAIL_HOST_PASSWORD,
        host: process.env.EMAIL_HOST,
        port: 993,
        tls: true
    },
    database: {
        host: process.env.DB_HOST,
        user: process.env.DB_USER,
        password: process.env.DB_PASSWORD,
        database: process.env.DB_NAME,
    }
};
const knex = Knex({
  client: 'pg',
  connection: config.database,
});

const getMessage = async msg => {
    return new Promise((resolve, reject) => {
        msg.on('body', function(stream, info) {
            var buffer = '';
            stream.on('data', function(chunk) {
                buffer += chunk.toString('utf8');
            });
            stream.once('end', function() {
                resolve(buffer);
            });
        });
    });
};

const fetchNewMails = async imap => {
    const box = await imap.openBoxAsync('INBOX', false);
    const results = await Promise.fromCallback(cb => imap.seq.search([ 'UNSEEN' ], cb));
    console.log('results', results)

    const toDelete = [];
    const handleMessage = async (msg, seqno) => {
        const bh = new BounceHandler();
        const buffer = await getMessage(msg);
        const [bounce] = bh.parse_email(buffer);
        if (!bounce) return;

        console.log('found bounce', bounce);
        await knex.transaction(async (trx) => {
            const ids = await (trx('inscriptions_mail')
                .where({
                    uid: bounce.messageid,
                    destinataires: [bounce.recipient],
                }).update({
                    error: bounce.status,
                }, ['id']))
            if (ids.length) {
                toDelete.push(seqno);
            }
            trx.commit();
        });
    };

    await new Promise((resolve, reject) => {
        var f = imap.seq.fetch(results, { bodies: '' });
        const promises = [];
        f.on('message', async (msg, seqno) => {
            try {
                await promises[promises.length - 1];
                promises.push(handleMessage(msg, seqno));
            } catch (err) {
                console.error('onMessage error', err);
            }
        });
        f.once('error', reject);
        f.once('end', () => resolve(Promise.all(promises)));
    });
    console.log('toDelete', toDelete);
    if (toDelete.length) {
        await Promise.fromCallback(cb => imap.seq.setFlags(toDelete, '\\Deleted', cb));
        await imap.expungeAsync();
    }
};

const imapConnect = (messageHandler) => {
    const imap = new Imap(config.imap);

    imap.once('ready', async function() {
        try {
            await fetchNewMails(imap);
            imap.on('mail', async () => {
                try {
                    await fetchNewMails(imap);
                } catch (err) {
                    console.error('onMail error', err);
                }
            });
        } catch (err) {
            console.error('imapConnect error', err);
        }
    });

    imap.once('error', function(err) {
        console.log('imap error', err);
    });

    imap.once('end', function() {
        console.log('Connection ended');
        process.exit();
    });

    imap.connect();
};

imapConnect();
