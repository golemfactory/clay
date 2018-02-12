# Ethereum Subsystem

## Introduction notes

1. Only public data is taken from Ethereum nodes. Private keys are kept and
   transactions are signed by Golem.
   
2. Standard keyfile format is used for keeping the Ethereum account private
   key. This allows backing up and recovering the private key with other tools.
   
3. Integration tests are needed. We can use geth in `--dev` mode to run 
   tests in preconfigured private Ethereum network.

## Modules

1. [Ethereum Node](#ethereum-node)

   Manages connection to and/or process of Ethereum node.

2. [Ethereum Account](#ethereum-account)

   Manages the password-protected Ethereum account private key.

3. [Payment Sender](#payment-sender)

   Responsible for sending scheduled payments to Ethereum network.

4. [Payment Monitor](#payment-monitor)

   Responsible for monitoring, confirming and matching incoming payments
   with expected incomes.

5. [Withdrawer](#withdrawer)?

   Capable of transferring tokens (GNT, ETH) by User request.
   
   
## Ethereum Node

The Ethereum Node module is responsible for:

1. Keeping the RPC connection to a Ethereum node instance via selected transport
   protocol (e.g. HTTP, Unix Socket, WebSocket).
  
2. Managing the Ethereum node process if to be managed by Golem Client.

3. Making sure the Ethereum node has correct configuration, is on the right
   blockchain, have good p2p connection, is synced. We want to offload this
   responsibility of (at least) collecting this information from Payment Sender.

The Ethereum Node is good mocking point for testing other modules. Current
implementation is in `golem.ethereum.client` and `golem.ethereum.node`
and should be merged into single Python module.


## Ethereum Account

The common solution is to keep the private key in a JSON file following
the [Web3 Secret Storage Definition] specification. There are at least 2 Python
implementations of this spec.

To sign an Ethereum transaction the account must be unlocked with
a User-provided password. There are multiple alternative scenarios how to handle
this problem.

### Unlock on startup

The password must be provided when Golem Client starts and the Ethereum Account
is unlocked all the time the Client is running. Payment Sender is able to sign
transaction without User attention.

### Unlock by UI when needed

The Ethereum Account module can provide a function to check whenever the account
is unlocked. The UI is responsible for unlocking the account if wants to perform
an action that requires signing Ethereum transactions. The account may be locked
again after some period of time.

This solution suffers from race conditions.

### Unlock on demand

The Ethereum Account module executes a callback function asking for password
when signing transaction is required. The callback is implemented by UI.
The account may be locked again after some period of time.


## Payment Sender

The Payment Sender receives payment sending requests with additional constraints
(e.g. a deadline within the payment must be confirmed)from other 
Golem Client modules.

The Payment Sender is operating in high latency environment (actions can take
minutes). The Payment Sender must have an internal persistent journal of 
requested actions. Optionally, Golem Client should keep running until Payment
Sender finishes performing scheduled jobs.

Other responsibilities:

- payment batching,
- deadlines,
- transaction cost estimation (use Ethereum node for this?),
- gas price selection strategy.

The exceptions to handle:

- transaction failed,
- transaction not confirmed for some time,
- no logs from transaction,
- transaction missing,
- low ETH balance,
- low GNT balance,
- unexpected balance change,
- bad Ethereum node connection.

Proper testing many of these exceptional situations is non-trivial.


## Payment Monitor

The Payment Monitor is responsible for monitoring incoming payments and matching
them with expected payments.

There is not enough information about payments in Ethereum state to match
individual payments. Instead, Payment Monitor keeps of balances per individual
Ethereum addresses (a FIFO queue per address). In this approach we don't have
to send other information offline but some expected payments might be partly
settled.

Payment Monitor only _reads_ Ethereum state. It does not need access to
Ethereum Account.


## Withdrawer

The job for Withdrawer is to allow transferring tokens from Ethereum Account
to an Ethereum address provided by User.

Optionally, we call also add an option to withdrawing automatically given the
balance reached some specified threshold.

Another idea for provider-only clients is to allow provide an external Ethereum
address for incoming payments.

At first this functionality was to be included in Payment Monitor, but I think
its better when features that require access to Ethereum Account are isolated. 


[Web3 Secret Storage Definition]: https://github.com/ethereum/wiki/wiki/Web3-Secret-Storage-Definition
