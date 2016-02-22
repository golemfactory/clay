# Ethereum Contracts for Golem
Ethereum contracts for nanopayments schemes used in Golem Worldwide Supercomputer.

## [Bank Of Deposit](BankOfDeposit.sol)

The Bank Of Deposit contract keeps user's ethers in contracts' internal storage.
This approach allows performing one-to-many payment scheme that is linearny cheaper than
series of individual Ethereum transactions.

## [Lottery](Lottery.sol)

The Lottery contract implements probabilistic one-to-many payments described in
[A Probabilistic Nanopayment Scheme for Golem](http://golemproject.net/doc/GolemNanopayments.pdf).
The contract allows organizing a lottery for multiple participants.
Only one of the participants become a winner and get the right to collect lottery's reward.

## Testing

The repository contains Python unit tests for the contracts. The pyethereum is used to implement the tests.
```
pip install -r requirements.txt
python -m unittest discover tests
```
