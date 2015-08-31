contract LotteryAgent {
    
    struct LotteryData {
        uint value;
        uint timeout;
        uint deposit;
        address winner;
        uint random;
    }
    
    mapping (bytes32 => LotteryData) lotteries;
    
	event Init(address indexed owner, bytes32 indexed descritionHash, uint value);
	event Winner(address indexed winner, bytes32 indexed descriptionHash);
	
	function initLottery(bytes32 descriptionHash, uint maturity, uint deposit) {
		LotteryData lottery = lotteries[descriptionHash];
		if (lottery.value != 0) 
		    return;
		lotteries[descriptionHash] = LotteryData(msg.value, maturity, deposit, 0);
		Init(msg.sender, descriptionHash, msg.value);
	}

	function getRandom(bytes32 descriptionHash) {
		LotteryData lottery = lotteries[descriptionHash];
	    if (lottery.value == 0 || lottery.winner != 0 | lottery.random != 0 ||
	    	block.number <= lottery.timeout)
	        return;
	}

	function winnerLottery(bytes32 descriptionHash) {
	    LotteryData lottery = lotteries[descriptionHash];
	    if (lottery.value == 0 || lottery.winner != 0 || block.number <= lottery.timeout || msg.value < lottery.deposit)
	        return;
	    lotteries[descriptionHash].deposit = msg.value;
	    lotteries[descriptionHash].winner = msg.sender;
	    lotteries[descriptionHash].timeout = block.number + 7200;
	    Winner(msg.sender, descriptionHash);
	}
	
	function payoutLottery(bytes32 descriptionHash) {
	    LotteryData lottery = lotteries[descriptionHash];
	    if (lottery.value == 0 || lottery.winner == 0 || block.number <= lottery.timeout)
	        return;
	    lottery.winner.send(lottery.value);
	    delete lotteries[descriptionHash];
	}

	function checkLottery(uint maturity, uint lotteryId, address[] participants, uint[] probabilities) external {
	    bytes32 descriptionHash = sha3(maturity, lotteryId, participants, probabilities);
	    LotteryData lottery = lotteries[descriptionHash];
	    if (lottery.value == 0 || (lottery.winner == 0 && block.number <= lottery.timeout))
	        return;
	    
		uint r = random(maturity);
		address winner;
		uint target = 0;
		for (uint i = 0; i < probabilities.length; ++i) {
			target += probabilities[i];
			if (r <= target) {
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
		return uint(block.blockhash(maturity));
	}
}
