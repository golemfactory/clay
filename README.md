# Ethereum Contracts for Golem
Ethereum contracts for nanopayment schemes used in [Golem Worldwide Supercomputer](http://golemproject.net).

## [Bank Of Deposit](BankOfDeposit.sol)

The Bank Of Deposit contract keeps users' ethers in contract's internal storage.
This approach allows performing one-to-many payment scheme that is linearly cheaper than
a series of individual Ethereum transactions.

## [Lottery](Lottery.sol)

The Lottery contract implements probabilistic one-to-many payments described in
[A Probabilistic Nanopayment Scheme for Golem](http://golemproject.net/doc/GolemNanopayments.pdf).
The contract allows organizing a lottery for multiple participants.
Only one of the participants becomes a winner and gets the right to collect the lottery's reward.

## Testing

The repository contains Python unit tests for the contracts. The [pyethereum](https://github.com/ethereum/pyethereum) is used to implement the tests.
```
pip install -r requirements.txt
python -m unittest discover tests
```
