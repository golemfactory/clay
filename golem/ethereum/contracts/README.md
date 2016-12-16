# Ethereum Contracts for Golem
Ethereum contracts for nanopayment schemes used in [Golem Worldwide Supercomputer](http://golemproject.net).

The contracts have been created thanks to the [BlockGrantX #1:Genesis](http://blockchainlabs.org/blockgrant-x-en).

Copyright © 2016

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the [GNU General Public License](LICENSE)
along with this program.  If not, see <http://www.gnu.org/licenses/>.

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
