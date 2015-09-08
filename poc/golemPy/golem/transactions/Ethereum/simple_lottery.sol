contract LotteryAgent {

    struct LotteryData {
        uint value;
        uint timeout;
        uint deposit;
        uint random;
        address payer;
        address winner;
    }

    mapping (bytes32 => LotteryData) lotteries;

	function initLottery(bytes32 descriptionHash, uint maturity, uint deposit) {
		LotteryData lottery = lotteries[descriptionHash];
		if (lottery.value != 0)
		    return;
		lotteries[descriptionHash] = LotteryData(msg.value, maturity, deposit, 0, msg.sender, 0);
	}

	function captureMaturityHash(bytes32 descriptionHash) {
	    LotteryData lottery = lotteries[descriptionHash];
	    if (lottery.value == 0 || lottery.random != 0 || block.number <= lottery.timeout ||
	    block.number > lottery.timeout + 256) {
	        return;
	    }
	    address sendTo = lottery.payer;
	    if (lottery.timeout + 128 < block.number)
	        sendTo = msg.sender;

	   lottery.random = random(lottery.timeout);
	   uint reward = lottery.value/10;
	   lottery.value -= reward;
	   sendTo.send(reward);
    }

	function winnerLottery(bytes32 descriptionHash) {
	    LotteryData lottery = lotteries[descriptionHash];
	    if (lottery.value == 0 || msg.value < lottery.deposit)
	        return;
	    if (lottery.random == 0 && block.number <= lottery.timeout + 128) {
	        return;
	    }
	    lottery.deposit = msg.value;
	    lottery.winner = msg.sender;

	    if (lottery.random == 0) {
	        lottery.random = random(lottery.timeout);
	    }
	    lottery.timeout = now + 86400;
	}

	function payoutLottery(bytes32 descriptionHash) {
	    LotteryData lottery = lotteries[descriptionHash];
	    if (lottery.value == 0 || lottery.winner == 0 || block.timestamp <= lottery.timeout)
	        return;
	    lottery.winner.send(lottery.value);
	    delete lotteries[descriptionHash];
	}

	function checkLottery(uint maturity, uint lotteryId, uint startValue, address[] participants, uint[] probabilities) external {
	    bytes32 descriptionHash = sha3(maturity, lotteryId, startValue, participants, probabilities);
	    LotteryData lottery = lotteries[descriptionHash];
	    if (lottery.value == 0 || (lottery.random == 0 && block.number <= lottery.timeout + 128))
	        return;

	    if (lottery.random == 0) {
	        lottery.random = random(lottery.timeout);
	    }

		address winner;
		uint target = 0;
		for (uint i = 0; i < probabilities.length; ++i) {
			target += probabilities[i];
			if (lottery.random <= target) {
				winner = participants[i];
				break;
			}
		}

		uint value = lotteries[descriptionHash].value;
		if (lotteries[descriptionHash].winner == 0) {
		    winner.send(value);
		} else {
		    if (winner != msg.sender) {
		        winner.send(value);
		        msg.sender.send(lotteries[descriptionHash].deposit);
		    } else {
		        winner.send(value + lotteries[descriptionHash].deposit);
		    }
		}
		delete lotteries[descriptionHash];

	}
	function random(uint maturity) internal constant returns(uint) {
	    while (block.number - maturity > 256) {
            maturity += 256;
	    }

		return uint(block.blockhash(maturity));
	}

	function verifyLottery(bytes32 descriptionHash) returns (bool) {
	    return lotteries[descriptionHash].value == 0;
	}
}
