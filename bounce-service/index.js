'use strict';
const Promise = require('bluebird');
const Imap = require('imap');
Promise.promisifyAll(Imap.prototype);
const { BounceHandler } = require('bounce-handler');
const Knex = require('knex');
const inspect = require('util').inspect;

const config = require('./config.json');
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

const handleMessage = async (msg, seqno) => {
    try {
        const bh = new BounceHandler();
        const buffer = await getMessage(msg);
        const [bounce] = bh.parse_email(buffer);
        if (!bounce) return;

        const ids = await knex('inscriptions_mail')
            .where({
                uid: bounce.messageid,
                destinataires: [bounce.recipient],
            }).update({
                error: bounce.status,
            }, ['id'])
        if (ids.length) {
            imap.addFlags(seqno, '\\Deleted', err => {
                if (err) console.error(err);
            });
        }
    } catch (err) {
        console.error(err);
    }
};

const fetchNewMails = async imap => {
    const box = await imap.openBoxAsync('INBOX', true);
    const results = await imap.searchAsync([ 'UNSEEN', ['SINCE', 'May 20, 2010'] ]);
    return new Promise((resolve, reject) => {
        var f = imap.seq.fetch(results, { bodies: '' });
        f.on('message', handleMessage);
        f.once('error', reject);
        f.once('end', resolve);
    });
};

const imapConnect = (messageHandler) => {
    const imap = new Imap(config.imap);

    imap.once('ready', async function() {
        try {
            await fetchNewMails(imap);
            imap.on('mails', async () => {
                try {
                    await fetchNewMails(imap);
                } catch (err) {
                    console.error(err);
                }
            });
        } catch (err) {
            console.error(err);
        }
    });

    imap.once('error', function(err) {
        console.log(err);
    });

    imap.once('end', function() {
        console.log('Connection ended');
        process.exit();
    });

    imap.connect();
};

imapConnect();
